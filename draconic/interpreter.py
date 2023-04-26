import abc
import ast
import contextlib
from collections.abc import Mapping, Sequence
from functools import cached_property

from .exceptions import *
from .helpers import DraconicConfig, OperatorMixin, zip_star
from .string import check_format_spec
from .versions import PY_310
from .types import approx_len_of

__all__ = ("SimpleInterpreter", "DraconicInterpreter")


# ===== single-line evaluator, noncompound types, etc =====
class SimpleInterpreter(OperatorMixin):
    """A simple interpreter capable of evaluating expressions. No compound types or assignments."""

    def __init__(self, builtins=None, config=None):
        if config is None:
            config = DraconicConfig()
        if builtins is None:
            builtins = {}

        super().__init__(config)

        if config.builtins_extend_default:
            builtins = {**config.default_names, **builtins}

        self.builtins = builtins

        self.nodes = {
            ast.Expr: self._eval_expr,
            # literals:
            ast.Num: self._eval_num,
            ast.Str: self._eval_str,
            ast.Constant: self._eval_constant,
            ast.FormattedValue: self._eval_formattedvalue,  # formatted value in f-string
            ast.JoinedStr: self._eval_joinedstr,  # f-string
            ast.NameConstant: self._eval_constant,  # True/False/None up to py3.7
            # names:
            ast.Name: self._eval_name,
            # ops:
            ast.UnaryOp: self._eval_unaryop,
            ast.BinOp: self._eval_binop,
            ast.BoolOp: self._eval_boolop,
            ast.Compare: self._eval_compare,
            ast.IfExp: self._eval_ifexp,
            # function call:
            ast.Call: self._eval_call,
            ast.keyword: self._eval_keyword,  # foo(x=y), kwargs (not supported)
            # container[key]:
            ast.Subscript: self._eval_subscript,
            ast.Index: self._eval_index,  # deprecated in py3.9 (bpo-34822)
            ast.Slice: self._eval_slice,  # deprecated in py3.9 (bpo-34822)
            # container.key:
            ast.Attribute: self._eval_attribute,
        }

        self._str = self._config.str
        self._expr = None  # save the expression for error handling

    def parse(self, expr: str):
        """
        Parses an expression.

        :type expr: str
        :rtype: list[ast.AST]
        """
        self._expr = expr
        try:
            return ast.parse(expr).body
        except SyntaxError as e:
            raise DraconicSyntaxError(e, expr) from e

    def eval(self, expr: str):
        """
        Evaluates an expression.

        :type expr: list[ast.AST] or str
        """
        expr = self.parse(expr)

        self._preflight()
        try:
            expression = expr[0]
        except IndexError:  # if there is no expression, evaluate to None
            return None
        return self._eval(expression)

    def _eval(self, node):
        """The internal evaluator used on each node in the parsed tree."""
        try:
            handler = self.nodes[type(node)]
        except KeyError:
            raise FeatureNotAvailable(
                "Sorry, {0} is not available in this evaluator".format(type(node).__name__), node, self._expr
            )

        try:
            return handler(node)
        except _PostponedRaise as pr:
            raise pr.cls(*pr.args, **pr.kwargs, node=node, expr=self._expr)
        except DraconicException:
            raise
        except Exception as e:
            raise AnnotatedException(e, node, self._expr) from e

    def _preflight(self):
        """Called before starting evaluation."""
        pass

    @property
    def names(self):
        return self.builtins

    @names.setter
    def names(self, new_names):
        self.builtins = new_names

    # ===== nodes =====
    def _eval_expr(self, node):
        return self._eval(node.value)

    @staticmethod
    def _eval_num(node):
        return node.n

    def _eval_str(self, node):
        if len(node.s) > self._config.max_const_len:
            raise IterableTooLong(
                f"String literal in statement is too long ({len(node.s)} > {self._config.max_const_len})",
                node,
                self._expr,
            )
        return self._str(node.s)

    def _eval_constant(self, node):
        if hasattr(node.value, "__len__") and len(node.value) > self._config.max_const_len:
            raise IterableTooLong(
                f"Literal in statement is too long ({len(node.value)} > {self._config.max_const_len})", node, self._expr
            )
        if isinstance(node.value, bytes):
            raise FeatureNotAvailable("Creation of bytes literals is not allowed", node, self._expr)
        return node.value

    def _eval_unaryop(self, node):
        return self.operators[type(node.op)](self._eval(node.operand))

    def _eval_binop(self, node):
        return self.operators[type(node.op)](self._eval(node.left), self._eval(node.right))

    def _eval_boolop(self, node):
        vout = False
        if isinstance(node.op, ast.And):
            for value in node.values:
                vout = self._eval(value)
                if not vout:
                    return vout
        elif isinstance(node.op, ast.Or):
            for value in node.values:
                vout = self._eval(value)
                if vout:
                    return vout
        return vout

    def _eval_compare(self, node):
        right = self._eval(node.left)
        to_return = True
        for operation, comp in zip(node.ops, node.comparators):
            if not to_return:
                break
            left = right
            right = self._eval(comp)
            to_return = self.operators[type(operation)](left, right)
        return to_return

    def _eval_ifexp(self, node):
        return self._eval(node.body) if self._eval(node.test) else self._eval(node.orelse)

    def _eval_call(self, node):
        func = self._eval(node.func)
        return func(*(self._eval(a) for a in node.args), **dict(self._eval(k) for k in node.keywords))

    def _eval_keyword(self, node):
        return node.arg, self._eval(node.value)

    def _eval_name(self, node):
        try:
            return self.names[node.id]
        except KeyError:
            raise NotDefined(f"{node.id} is not defined", node, self._expr)

    def _eval_subscript(self, node):
        container = self._eval(node.value)
        key = self._eval(node.slice)
        try:
            return container[key]
        except KeyError:
            raise

    def _eval_attribute(self, node):
        for prefix in self._config.disallow_prefixes:
            if node.attr.startswith(prefix):
                raise FeatureNotAvailable(f"Access to the {node.attr} attribute is not allowed", node, self._expr)
        if node.attr in self._config.disallow_methods:
            raise FeatureNotAvailable(f"Access to the {node.attr} attribute is not allowed", node, self._expr)
        # eval node
        node_evaluated = self._eval(node.value)

        # Maybe the base object is an actual object, not just a dict
        try:
            return getattr(node_evaluated, node.attr)
        except (AttributeError, TypeError):
            # If it is not present, raise an exception
            raise NotDefined(f"'{type(node_evaluated).__name__}' object has no attribute {node.attr}", node, self._expr)

    def _eval_index(self, node):
        return self._eval(node.value)

    def _eval_slice(self, node):
        lower = upper = step = None
        if node.lower is not None:
            lower = self._eval(node.lower)
        if node.upper is not None:
            upper = self._eval(node.upper)
        if node.step is not None:
            step = self._eval(node.step)
        return slice(lower, upper, step)

    def _eval_joinedstr(self, node):
        length = 0
        evaluated_values = []
        for n in node.values:
            val = str(self._eval(n))
            length += len(val)
            if length > self._config.max_const_len:
                raise IterableTooLong(
                    f"f-string in statement is too long ({length} > {self._config.max_const_len})", node, self._expr
                )
            evaluated_values.append(val)
        return "".join(evaluated_values)

    def _eval_formattedvalue(self, node):
        if node.format_spec:
            format_spec = str(self._eval(node.format_spec))
            check_format_spec(self._config, format_spec)
            return self._str(format(self._eval(node.value), format_spec))
        return self._eval(node.value)


# ===== multiple-line execution, assignment, compound types =====
class _Break:
    __slots__ = ("node",)

    def __init__(self, node: ast.Break):
        self.node = node


class _Continue:
    __slots__ = ("node",)

    def __init__(self, node: ast.Continue):
        self.node = node


class _Return:
    __slots__ = ("value", "node")

    def __init__(self, retval, node: ast.Return):
        self.value = retval
        self.node = node


class _Callable(abc.ABC):
    """ABC for functions and lambdas"""

    def __init__(self, interpreter, node, names_at_def, defining_expr):
        self._interpreter = interpreter
        self._node = node
        self._outer_scope_names = names_at_def
        self._defining_expr = defining_expr

    # faux introspection props since __dunders__ aren't accessible
    @property
    def name(self):
        return self.__name__

    @cached_property
    def doc(self):
        return ast.get_docstring(self._node)

    def __call__(self, *args, **kwargs):
        raise NotImplementedError


class _Function(_Callable):
    """A wrapper class around an ast.FunctionDef."""

    def __init__(self, interpreter, functiondef, names_at_def, defining_expr):
        super().__init__(interpreter, functiondef, names_at_def, defining_expr)
        self.__name__ = self._name = functiondef.name

    def __repr__(self):
        return f"<Function {self._name}>"

    def __call__(self, *args, **kwargs):
        try:
            # noinspection PyProtectedMember
            return self._interpreter._exec_function(self, *args, **kwargs)
        except DraconicException as e:
            e.__drac_context__ = self._name
            raise


class _Lambda(_Callable):
    """A wrapper class around an ast.Lambda."""

    def __init__(self, interpreter, lambdadef, names_at_def, defining_expr):
        super().__init__(interpreter, lambdadef, names_at_def, defining_expr)
        self.__name__ = self._name = "<lambda>"

    def __repr__(self):
        return f"<Function <lambda>>"

    @property
    def doc(self):
        return None

    def __call__(self, *args, **kwargs):
        try:
            # noinspection PyProtectedMember
            return self._interpreter._exec_lambda(self, *args, **kwargs)
        except DraconicException as e:
            e.__drac_context__ = self._name
            raise


class DraconicInterpreter(SimpleInterpreter):
    """The Draconic interpreter. Capable of running Draconic code."""

    def __init__(self, builtins=None, config=None, initial_names=None):
        super().__init__(builtins, config)

        if initial_names is None:
            initial_names = {}

        self.nodes.update(
            {
                # compound types:
                ast.Dict: self._eval_dict,
                ast.Tuple: self._eval_tuple,
                ast.List: self._eval_list,
                ast.Set: self._eval_set,
                # comprehensions:
                ast.ListComp: self._eval_listcomp,
                ast.SetComp: self._eval_setcomp,
                ast.DictComp: self._eval_dictcomp,
                ast.GeneratorExp: self._eval_generatorexp,
                ast.Starred: self._eval_starred,  # foo(*iterable), [*iterable], etc.
                # assignments:
                ast.Assign: self._eval_assign,
                ast.AugAssign: self._eval_augassign,
                ast.NamedExpr: self._eval_namedexpr,
                # control:
                ast.Return: self._exec_return,
                ast.If: self._exec_if,
                ast.For: self._exec_for,
                ast.While: self._exec_while,
                ast.Break: lambda node: _Break(node),
                ast.Continue: lambda node: _Continue(node),
                ast.Pass: lambda node: None,
                # functions:
                ast.FunctionDef: self._eval_functiondef,
                ast.Lambda: self._eval_lambda,
                # try/except:
                ast.Try: self._exec_try,
            }
        )

        self.assign_nodes = {
            ast.Name: self._assign_name,
            ast.Tuple: self._assign_unpack,
            ast.List: self._assign_unpack,
            ast.Subscript: self._assign_subscript,
            # no assigning to attributes
            ast.Starred: self._assign_starred,  # a, *b = [x, y, z]
        }

        self.patma_nodes = {}

        if PY_310:
            self.nodes.update(
                {
                    ast.Match: self._exec_match,
                }
            )

            self.patma_nodes.update(
                {
                    ast.MatchValue: self._patma_match_value,
                    ast.MatchSingleton: self._patma_match_singleton,
                    ast.MatchSequence: self._patma_match_sequence,
                    ast.MatchMapping: self._patma_match_mapping,
                    ast.MatchStar: self._patma_match_star,
                    # no MatchClass
                    ast.MatchAs: self._patma_match_as,
                    ast.MatchOr: self._patma_match_or,
                }
            )

        # compound type helpers
        self._list = self._config.list
        self._set = self._config.set
        self._dict = self._config.dict

        self._num_stmts = 0
        self._loops = 0
        self._depth = 1
        self._names = initial_names

    def eval(self, expr: str):
        retval = super().eval(expr)
        if isinstance(retval, _Return):
            return retval.value
        elif isinstance(retval, (_Break, _Continue)):
            raise DraconicSyntaxError.from_node(retval.node, msg="Loop control outside loop", expr=self._expr)
        return retval

    def execute(self, expr: str):
        """Executes an AST body."""
        expr = self.parse(expr)

        self._preflight()
        retval = self._exec(expr)
        if isinstance(retval, (_Break, _Continue)):
            raise DraconicSyntaxError.from_node(retval.node, msg="Loop control outside loop", expr=self._expr)
        if isinstance(retval, _Return):
            return retval.value

    def execute_module(self, expr: str, module_name="<module>"):
        """
        Executes the expression as if it was a module.
        This is similar to *execute* except:
        - it doesn't allow bare returns
        - it doesn't call preflight
        - it saves the previously running expression
        - it sets the exception context
        """
        old_expr = self._expr
        try:
            expr = self.parse(expr)
            retval = self._exec(expr)
            if isinstance(retval, (_Break, _Continue)):
                raise DraconicSyntaxError.from_node(retval.node, msg="Loop control outside loop", expr=self._expr)
            if isinstance(retval, _Return):
                raise DraconicSyntaxError.from_node(retval.node, msg="'return' outside function", expr=self._expr)
        except DraconicException as e:
            e.__drac_context__ = module_name
            raise
        finally:
            self._expr = old_expr

    def _preflight(self):
        self._num_stmts = 0
        self._loops = 0
        super()._preflight()

    def _eval(self, node):
        self._num_stmts += 1
        if self._num_stmts > self._config.max_statements:
            raise TooManyStatements("You are trying to execute too many statements.", node, self._expr)

        val = super()._eval(node)
        # ensure that it's always an instance of our safe compound types being returned
        # note: makes a copy, so the original copy won't be updated
        # we don't use isinstance because we're looking for very specific classes
        if type(val) is str:
            return self._str(val)
        elif type(val) is list:
            return self._list(val)
        elif type(val) is dict:
            return self._dict(val)
        elif type(val) is set:
            return self._set(val)
        return val

    def _exec(self, body):
        for expression in body:
            retval = self._eval(expression)
            if isinstance(retval, (_Return, _Break, _Continue)):
                return retval

    @property
    def names(self):
        return {**self.builtins, **self._names}

    @names.setter
    def names(self, new_names):
        self._names = new_names

    # ===== compound types =====
    def _eval_dict(self, node):
        return self._dict(self._starred_keyword_unwrap(zip(node.keys, node.values)))

    def _eval_tuple(self, node):
        return tuple(self._starred_unwrap(node.elts))

    def _eval_list(self, node):
        return self._list(self._starred_unwrap(node.elts))

    def _eval_set(self, node):
        return self._set(self._starred_unwrap(node.elts))

    def _eval_listcomp(self, node):
        return self._list(self._do_comprehension(node))

    def _eval_setcomp(self, node):
        return self._set(self._do_comprehension(node))

    def _eval_dictcomp(self, node):
        return self._dict(self._do_comprehension(node, is_dictcomp=True))

    def _eval_generatorexp(self, node):
        for item in self._do_comprehension(node):
            yield item

    def _do_comprehension(self, comprehension_node, is_dictcomp=False):
        if is_dictcomp:

            def do_value(node):
                return self._eval(node.key), self._eval(node.value)

        else:

            def do_value(node):
                return self._eval(node.elt)

        extra_names = {}
        previous_name_evaller = self.nodes[ast.Name]

        def eval_names_extra(node):
            """
            Here we hide our extra scope for within this comprehension
            """
            if node.id in extra_names:
                return extra_names[node.id]
            return previous_name_evaller(node)

        self.nodes.update({ast.Name: eval_names_extra})

        def recurse_targets(target, value):
            """
                Recursively (enter, (into, (nested, name), unpacking)) = \
                             and, (assign, (values, to), each
            """
            if isinstance(target, ast.Name):
                extra_names[target.id] = value
            else:
                for t, v in zip(target.elts, value):
                    recurse_targets(t, v)

        def do_generator(gi=0, total_len=0):
            """
            For each generator, set the names used in the final emitted value/the next generator.
            Only the final generator (gi = len(comprehension_node.generator)-1) should emit the final values,
            since only then are all possible necessary values set in extra_names.
            """
            generator_node = comprehension_node.generators[gi]
            for i in self._eval(generator_node.iter):
                self._loops += 1
                if self._loops > self._config.max_loops:
                    raise IterableTooLong("Comprehension generates too many elements", comprehension_node, self._expr)

                # set names
                recurse_targets(generator_node.target, i)

                if all(self._eval(iff) for iff in generator_node.ifs):
                    if len(comprehension_node.generators) > gi + 1:
                        # next generator
                        yield from do_generator(gi + 1, total_len)  # bubble up emitted values
                    else:
                        # emit values
                        value = do_value(comprehension_node)
                        total_len += sum(approx_len_of(val) for val in value) if is_dictcomp else approx_len_of(value)
                        total_len += 1
                        if total_len > self._config.max_const_len:
                            raise IterableTooLong("Comprehension generates too much", comprehension_node, self._expr)
                        yield value

        try:
            yield from do_generator()
        finally:
            self.nodes.update({ast.Name: previous_name_evaller})

    def _eval_starred(self, node):
        raise DraconicSyntaxError.from_node(node, "can't use starred expression here", self._expr)

    def _starred_unwrap(self, nodes, *, check_len=True):
        total_len = 0

        for node in nodes:
            if type(node) is ast.Starred:
                evalue = self._eval(node.value)
                try:
                    for retval in evalue:
                        self._loops += 1
                        if self._loops > self._config.max_loops:
                            raise IterableTooLong("Unwrapping generates too many elements", node, self._expr)
                        if check_len:
                            total_len += approx_len_of(retval) + 1
                            if total_len > self._config.max_const_len:
                                raise IterableTooLong("Unwrapping generates too much", node, self._expr)
                        yield retval
                except TypeError:
                    raise TypeError(f"Value after * must be iterable, got {type(evalue).__name__}")
            else:
                retval = self._eval(node)
                if check_len:
                    total_len += approx_len_of(retval) + 1
                    if total_len > self._config.max_const_len:
                        raise IterableTooLong("Unwrapping generates too much", node, self._expr)
                yield retval

    def _starred_keyword_unwrap(self, items, *, check_len=True):
        total_len = 0

        for key, value in items:
            evalue = self._eval(value)
            if key is None:
                if isinstance(evalue, Mapping):
                    for retval in evalue.items():
                        self._loops += 1
                        if self._loops > self._config.max_loops:
                            raise IterableTooLong("Unwrapping generates too many elements", value, self._expr)
                        if check_len:
                            total_len += sum(approx_len_of(val) for val in retval) + 1
                            if total_len > self._config.max_const_len:
                                raise IterableTooLong("Unwrapping generates too much", value, self._expr)
                        yield retval
                else:
                    raise TypeError(f"argument after ** must be a mapping, got {type(value).__name__}")
            else:
                retval = self._eval(key) if isinstance(key, ast.AST) else key, evalue
                if check_len:
                    total_len += sum(approx_len_of(val) for val in retval) + 1
                    if total_len > self._config.max_const_len:
                        raise IterableTooLong("Unwrapping generates too much", value, self._expr)
                yield retval

    # ===== assignments =====
    def _eval_assign(self, node):
        value = self._eval(node.value)
        for target in node.targets:  # a = b = 1
            self._assign(target, value)

    def _eval_augassign(self, node):
        target = node.target
        # transform a += 1 to a = a + 1, then we can use assign and eval
        new_value = ast.BinOp(left=target, op=node.op, right=node.value)
        ast.copy_location(new_value, target)
        self._assign(target, self._eval_binop(new_value))

    def _eval_namedexpr(self, node):
        value = self._eval(node.value)
        self._assign(node.target, value)
        return value

    # ---- primary assign branch ----
    def _assign(self, names, values):
        try:
            handler = self.assign_nodes[type(names)]
        except KeyError:
            raise FeatureNotAvailable(f"Assignment to {type(names).__name__} is not allowed", names, self._expr)
        # noinspection PyArgumentList
        return handler(names, values)

    def _assign_name(self, name, value):
        if name.id in self.builtins:
            raise DraconicValueError(f"{name.id} is already builtin (no shadow assignments).", name, self._expr)
        self._names[name.id] = value

    def _assign_subscript(self, name, value):
        container = self._eval(name.value)
        key = self._eval(name.slice)
        container[key] = value  # no further evaluation needed, if container is in names it will update

    def _assign_unpack(self, names, values):
        if not isinstance(names, (ast.Tuple, ast.List)):
            self._assign(names, values)
        else:
            try:
                values = list(iter(values))
            except TypeError:
                raise DraconicValueError(
                    f"Cannot unpack non-iterable {type(values).__name__} object", names, self._expr
                )

            stars = (i for i in names.elts if type(i) is ast.Starred)
            starred = next(stars, None)

            if starred is None:
                if len(names.elts) > len(values):
                    raise DraconicValueError(
                        f"not enough values to unpack (expected {len(names.elts)}, got {len(values)})",
                        names,
                        self._expr,
                    )
                elif len(names.elts) < len(values):
                    raise DraconicValueError(
                        f"too many values to unpack (expected {len(names.elts)}, got {len(values)})",
                        names,
                        self._expr,
                    )
                for t, v in zip(names.elts, values):
                    self._assign_unpack(t, v)
            elif (extra := next(stars, None)) is not None:
                raise DraconicSyntaxError.from_node(extra, "multiple starred expressions in assignment", self._expr)
            else:
                if len(values) < (len(names.elts) - 1):
                    raise DraconicValueError(
                        f"not enough values to unpack (expected at least {len(names.elts) - 1}, got {len(values)})",
                        names,
                        self._expr,
                    )

                for t, v in zip_star(names.elts, values, star_index=names.elts.index(starred)):
                    self._assign_unpack(t, v)

    def _assign_starred(self, name, value):
        self._assign_name(name.value, value)

    # ===== execution =====
    def _exec_return(self, node):
        retval = self._eval(node.value) if node.value is not None else None
        return _Return(retval, node)

    def _exec_if(self, node):
        test = self._eval(node.test)
        if test:
            return self._exec(node.body)
        else:
            return self._exec(node.orelse)

    def _exec_for(self, node):
        for item in self._eval(node.iter):
            self._loops += 1
            if self._loops > self._config.max_loops:
                raise TooManyStatements("Too many loops (in for block)", node, self._expr)

            self._assign(node.target, item)
            retval = self._exec(node.body)
            if isinstance(retval, _Return):
                return retval
            elif isinstance(retval, _Break):
                break
            elif isinstance(retval, _Continue):
                continue
        else:
            return self._exec(node.orelse)

    def _exec_while(self, node):
        while self._eval(node.test):
            self._loops += 1
            if self._loops > self._config.max_loops:
                raise TooManyStatements("Too many loops (in while block)", node, self._expr)

            retval = self._exec(node.body)
            if isinstance(retval, _Return):
                return retval
            elif isinstance(retval, _Break):
                break
            elif isinstance(retval, _Continue):
                continue
        else:
            return self._exec(node.orelse)

    # ===== patma =====
    # impl inspired by GVR's impl at https://github.com/gvanrossum/patma/blob/master/patma.py
    # note: we do duplicate binding checks at runtime instead of preflight, which means that
    # some code could run before the duplicate binding is detected, and certain exprs illegal in Python are legal here
    # this is OK for our use case but differs from Python's impl
    def _exec_match(self, node):
        subject = self._eval(node.subject)
        for match_case in node.cases:
            if (bindings := self._patma(match_case.pattern, subject)) is not None:
                self._names.update(bindings)  # In python patma, values are bound before the guard executes
                if match_case.guard is not None and not self._eval(match_case.guard):
                    continue
                return self._exec(match_case.body)

    def _patma(self, pattern, subject):
        """
        Execute matching logic for a given match_case and subject.
        If the subject matches the case, return the dict of bindings for this case.
        Otherwise, return None.
        """
        try:
            handler = self.patma_nodes[type(pattern)]
        except KeyError:
            raise FeatureNotAvailable(f"Matching on {type(pattern).__name__} is not allowed", pattern, self._expr)
        self._num_stmts += 1
        return handler(pattern, subject)

    def _patma_match_value(self, node, subject):
        if subject == self._eval(node.value):
            return {}
        return None

    @staticmethod
    def _patma_match_singleton(node, subject):
        if subject is node.value:
            return {}
        return None

    def _patma_match_sequence(self, node, subject):
        if not isinstance(subject, Sequence) or isinstance(subject, (str, bytes)):
            return None

        match_star_idxs = [idx for idx, pattern in enumerate(node.patterns) if isinstance(pattern, ast.MatchStar)]
        if len(match_star_idxs) > 1:
            # multiple starred names
            raise DraconicValueError(f"multiple starred names in sequence pattern", node, self._expr)
        elif match_star_idxs:
            # one starred name
            if not len(node.patterns) <= len(subject) + 1:
                return None
            pattern_iterator = zip_star(node.patterns, subject, star_index=match_star_idxs[0])
        else:
            # no starred names
            if len(node.patterns) != len(subject):
                return None
            pattern_iterator = zip(node.patterns, subject)

        # do iteration over patterns and values
        bindings = {}
        bound_names = set()
        for pattern, item in pattern_iterator:
            # recursive check
            # noinspection DuplicatedCode
            match = self._patma(pattern, item)
            if match is None:
                return None

            # duplicate bindings check
            if bound_names.intersection(match):
                raise DraconicValueError(
                    f"multiple assignment to names {sorted(bound_names.intersection(match))} in sequence pattern",
                    node,
                    self._expr,
                )
            bindings.update(match)
            bound_names.update(match)

        return bindings

    def _patma_match_mapping(self, node, subject):
        if not isinstance(subject, Mapping):
            return None

        bindings = {}
        bound_names = set()
        bound_keys = set()
        for key, pattern in zip(node.keys, node.patterns):
            # recursive check
            key = self._eval(key)
            try:
                value = subject[key]
            except KeyError:
                return None
            # noinspection DuplicatedCode
            match = self._patma(pattern, value)
            if match is None:
                return None

            # duplicate bindings check
            if bound_names.intersection(match):
                raise DraconicValueError(
                    f"multiple assignment to names {sorted(bound_names.intersection(match))} in mapping pattern",
                    node,
                    self._expr,
                )
            bindings.update(match)
            bound_names.update(match)
            bound_keys.add(key)

        if node.rest is not None:
            if node.rest in bound_names:
                raise DraconicValueError(
                    f"multiple assignment to name {node.rest!r} in mapping pattern", node, self._expr
                )
            bindings[node.rest] = {k: v for k, v in subject.items() if k not in bound_keys}

        return bindings

    @staticmethod
    def _patma_match_star(node, subject):
        if node.name is None:
            return {}
        return {node.name: subject}

    def _patma_match_as(self, node, subject):
        if node.name is None:  # this is the wildcard pattern, always matches
            return {}
        if node.pattern is None:  # bare name capture pattern, always matches
            return {node.name: subject}
        # otherwise if the inner match matches, we just add an additional binding to it
        inner_match = self._patma(node.pattern, subject)
        if inner_match is None:
            return None
        return {**inner_match, node.name: subject}

    def _patma_match_or(self, node, subject):
        # since we don't know the subpattern's bindings until it executes, we can't enforce both sides having the
        # same bindings like in Python
        for pattern in node.patterns:
            match = self._patma(pattern, subject)
            if match is not None:
                return match
        return None

    # ===== functions =====
    # definitions
    def _eval_functiondef(self, node):
        if node.name in self.builtins:
            raise DraconicValueError(f"{node.name} is already builtin (no shadow assignments).", node, self._expr)
        self._names[node.name] = _Function(self, node, self._names, self._expr)

    def _eval_lambda(self, node):
        return _Lambda(self, node, self._names, self._expr)

    # executions
    def _eval_call(self, node):
        func = self._eval(node.func)
        args = tuple(self._starred_unwrap(node.args, check_len=False))
        kwargs = dict(self._starred_keyword_unwrap(((k.arg, k.value) for k in node.keywords), check_len=False))
        try:
            return func(*args, **kwargs)
        except DraconicException as e:
            raise NestedException(e.msg, node, self._expr, last_exc=e) from e

    # noinspection PyProtectedMember
    @contextlib.contextmanager
    def _function_call_context(self, __functiondef, /, *args, **kwargs):
        # check limits
        self._depth += 1
        if self._depth > self._config.max_recursion_depth:
            _raise_in_context(TooMuchRecursion, "Maximum recursion depth exceeded")
        # store current names and expression
        old_names = self._names
        old_expr = self._expr
        # bind closure names and contextual expression
        self._names = __functiondef._outer_scope_names.copy()
        self._expr = __functiondef._defining_expr

        # yield control to the call
        try:
            self._bind_function_args(__functiondef, *args, **kwargs)
            yield
        finally:
            # restore old names and expr
            self._names = old_names
            self._expr = old_expr
            # reduce recursion depth
            self._depth -= 1

    # noinspection PyProtectedMember
    def _bind_function_args(self, __functiondef, /, *args, **kwargs):
        # check and bind args
        arguments = __functiondef._node.args
        # check valid pos num
        if len(args) > (numpos := len(arguments.posonlyargs) + len(arguments.args)) and arguments.vararg is None:
            raise TypeError(f"{__functiondef._name}() takes {numpos} positional arguments but {len(args)} were given")
        args_i = 0
        default_i = len(arguments.defaults) - numpos
        # posonly
        for posonly in arguments.posonlyargs:
            if args_i + 1 > len(args):
                if default_i < 0:
                    raise TypeError(f"{__functiondef._name}() missing required positional argument: {posonly.arg!r}")
                self._names[posonly.arg] = self._eval(arguments.defaults[default_i])
            else:
                self._names[posonly.arg] = args[args_i]
            args_i += 1
            default_i += 1
        # normal
        for posarg in arguments.args:
            # at least 1
            if args_i + 1 > len(args) and posarg.arg not in kwargs:
                if default_i < 0:
                    raise TypeError(f"{__functiondef._name}() missing required positional argument: {posarg.arg!r}")
                self._names[posarg.arg] = self._eval(arguments.defaults[default_i])
            # pos and kw
            elif args_i + 1 <= len(args) and posarg.arg in kwargs:
                raise TypeError(f"{__functiondef._name}() got multiple values for argument {posarg.arg!r}")
            elif posarg.arg in kwargs:
                self._names[posarg.arg] = kwargs.pop(posarg.arg)
            else:
                # we won't indexerror because if it's not in kwargs and args_i is invalid, the first if catches it
                self._names[posarg.arg] = args[args_i]
            args_i += 1
            default_i += 1
        # kwargonly
        for k_i, kwargonly in enumerate(arguments.kwonlyargs):
            if kwargonly.arg not in kwargs and arguments.kw_defaults[k_i] is None:
                raise TypeError(f"{__functiondef._name}() missing required keyword argument: {kwargonly.arg!r}")
            if kwargonly.arg in kwargs:
                self._names[kwargonly.arg] = kwargs.pop(kwargonly.arg)
            else:
                self._names[kwargonly.arg] = self._eval(arguments.kw_defaults[k_i])
        # *args
        if arguments.vararg is not None:
            if approx_len_of(args[args_i:]) > self._config.max_const_len:
                _raise_in_context(IterableTooLong, f"*{arguments.vararg.arg} would be too large")
            self._names[arguments.vararg.arg] = tuple(args[args_i:])
        # **kwargs
        if arguments.kwarg is not None:
            if approx_len_of(kwargs) > self._config.max_const_len:
                _raise_in_context(IterableTooLong, f"**{arguments.kwarg.arg} would be too large")
            self._names[arguments.kwarg.arg] = kwargs
        elif kwargs:  # and arguments.kwarg is None (implicit)
            raise TypeError(f"{__functiondef._name}() got unexpected keyword arguments: {tuple(kwargs.keys())}")

    # noinspection PyProtectedMember
    def _exec_function(self, __functiondef: _Function, /, *args, **kwargs):
        with self._function_call_context(__functiondef, *args, **kwargs):
            retval = self._exec(__functiondef._node.body)
            if isinstance(retval, (_Break, _Continue)):
                raise DraconicSyntaxError.from_node(retval.node, msg="Loop control outside loop", expr=self._expr)
            if isinstance(retval, _Return):
                return retval.value

    # noinspection PyProtectedMember
    def _exec_lambda(self, __lambdadef: _Lambda, /, *args, **kwargs):
        with self._function_call_context(__lambdadef, *args, **kwargs):
            return self._eval(__lambdadef._node.body)

    # ===== try/except =====
    def _exec_try(self, node: ast.Try):
        try:
            retval = self._exec(node.body)
            if isinstance(retval, (_Return, _Continue, _Break)):
                return retval
        except Exception as exc:
            if isinstance(exc, WrappedException):
                exc = exc.original
            # draconic diff: limit errors cannot be caught
            if isinstance(exc, LimitException):
                raise
            # enter into the except handlers
            for handler in node.handlers:
                if self._except_handler_matches(handler, exc):
                    retval = self._except_handler(handler)
                    if isinstance(retval, (_Return, _Continue, _Break)):
                        return retval
                    break
            else:
                raise
        else:
            retval = self._exec(node.orelse)
            if isinstance(retval, (_Return, _Continue, _Break)):
                return retval
        finally:
            retval = self._exec(node.finalbody)
            if isinstance(retval, (_Return, _Continue, _Break)):
                return retval

    def _except_handler_matches(self, node: ast.ExceptHandler, exc: BaseException) -> bool:
        # draconic diff: exception handlers must be string literals, tuple[str] literals, or bare
        if node.type is None:
            return True
        if isinstance(node.type, ast.Str):
            return type(exc).__name__ == self._eval_str(node.type)
        elif isinstance(node.type, ast.Tuple):
            if not all(isinstance(item, ast.Str) for item in node.type.elts):
                raise FeatureNotAvailable(
                    "'except' clause expressions must be string literals or tuple of string literals", node, self._expr
                )
            return type(exc).__name__ in self._eval_tuple(node.type)
        else:
            raise FeatureNotAvailable(
                "'except' clause expressions must be string literals or tuple of string literals", node, self._expr
            )

    def _except_handler(self, node: ast.ExceptHandler):
        # draconic diff: 'as X' clause not allowed
        if node.name is not None:
            raise FeatureNotAvailable("'except ... as X' is not available in this interpreter", node, self._expr)
        # run body
        return self._exec(node.body)
