import ast

from .exceptions import *
from .helpers import DraconicConfig, OperatorMixin, safe_dict, safe_list, safe_set

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
            ast.Index: self._eval_index,
            ast.Slice: self._eval_slice,
            # container.key:
            ast.Attribute: self._eval_attribute,
        }

    @staticmethod
    def parse(expr):
        """
        Parses an expression.

        :type expr: str
        :rtype: list[ast.AST]
        """
        try:
            return ast.parse(expr).body
        except SyntaxError as e:
            raise DraconicSyntaxError(e)

    def eval(self, expr):
        """
        Evaluates an expression.

        :type expr: list[ast.AST] or str
        """
        if not isinstance(expr, list):
            expr = self.parse(expr)

        self._preflight()
        expression = expr[0]
        return self._eval(expression)

    def _eval(self, node):
        """ The internal evaluator used on each node in the parsed tree. """
        try:
            handler = self.nodes[type(node)]
        except KeyError:
            raise FeatureNotAvailable("Sorry, {0} is not available in this "
                                      "evaluator".format(type(node).__name__), node)

        try:
            return handler(node)
        except _PostponedRaise as pr:
            raise pr.cls(*pr.args, **pr.kwargs, node=node)
        except DraconicException:
            raise
        except Exception as e:
            raise AnnotatedException(e, node)

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
                f"String literal in statement is too long ({len(node.s)} > {self._config.max_const_len})", node)
        return node.s

    def _eval_constant(self, node):
        if hasattr(node.value, '__len__') and len(node.value) > self._config.max_const_len:
            raise IterableTooLong(
                f"Literal in statement is too long ({len(node.value)} > {self._config.max_const_len})", node)
        return node.value

    def _eval_unaryop(self, node):
        return self.operators[type(node.op)](self._eval(node.operand))

    def _eval_binop(self, node):
        return self.operators[type(node.op)](self._eval(node.left),
                                             self._eval(node.right))

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
        return self._eval(node.body) if self._eval(node.test) \
            else self._eval(node.orelse)

    def _eval_call(self, node):
        func = self._eval(node.func)
        return func(
            *(self._eval(a) for a in node.args),
            **dict(self._eval(k) for k in node.keywords)
        )

    def _eval_keyword(self, node):
        return node.arg, self._eval(node.value)

    def _eval_name(self, node):
        try:
            return self.names[node.id]
        except KeyError:
            raise NotDefined(f"{node.id} is not defined", node)

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
                raise FeatureNotAvailable(f"Access to the {node.attr} attribute is not allowed", node)
        if node.attr in self._config.disallow_methods:
            raise FeatureNotAvailable(f"Access to the {node.attr} attribute is not allowed", node)
        # eval node
        node_evaluated = self._eval(node.value)

        # Maybe the base object is an actual object, not just a dict
        try:
            return getattr(node_evaluated, node.attr)
        except (AttributeError, TypeError):
            pass

        # Try and look for [x] if .x doesn't work
        try:
            return node_evaluated[node.attr]
        except (KeyError, TypeError):
            pass

        # If it is neither, raise an exception
        raise NotDefined(f"'{type(node_evaluated).__name__}' object has no attribute {node.attr}", node)

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
                raise IterableTooLong(f"f-string in statement is too long ({length} > {self._config.max_const_len})",
                                      node)
            evaluated_values.append(val)
        return ''.join(evaluated_values)

    def _eval_formattedvalue(self, node):
        if node.format_spec:
            fmt = "{:" + self._eval(node.format_spec) + "}"
            return fmt.format(self._eval(node.value))
        return self._eval(node.value)


# ===== multiple-line execution, assignment, compound types =====
class DraconicInterpreter(SimpleInterpreter):
    """The Draconic interpreter. Capable of running Draconic code."""

    class _FinalValue:
        def __init__(self, value):
            self.value = value

    class _Return(BaseException):
        """We propogate a ``return`` up by using a custom exception."""

        def __init__(self, retval):
            self.value = retval

    class _Break(BaseException):
        pass

    class _Continue(BaseException):
        pass

    def __init__(self, builtins=None, config=None, initial_names=None):
        super(DraconicInterpreter, self).__init__(builtins, config)

        if initial_names is None:
            initial_names = {}

        self.nodes.update({
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
            # assignments:
            ast.Assign: self._eval_assign,
            ast.AugAssign: self._eval_augassign,
            self._FinalValue: lambda v: v.value,
            # control:
            ast.Return: self._exec_return,
            ast.If: self._exec_if,
            ast.For: self._exec_for,
            ast.While: self._exec_while,
            ast.Break: self._exec_break,
            ast.Continue: self._exec_continue,
            ast.Pass: lambda node: None
        })

        if hasattr(ast, 'NamedExpr'):
            self.nodes.update({
                ast.NamedExpr: self._eval_namedexpr
            })

        self.assign_nodes = {
            ast.Name: self._assign_name,
            ast.Tuple: self._assign_unpack,
            ast.List: self._assign_unpack,
            ast.Subscript: self._assign_subscript,
            # no assigning to attributes
        }

        # compound type helpers
        self._list = self._config.list
        self._set = self._config.set
        self._dict = self._config.dict

        self._num_stmts = 0
        self._loops = 0
        self._names = initial_names

    def eval(self, expr):
        try:
            return super().eval(expr)
        except self._Return as r:
            return r.value
        except (self._Break, self._Continue):
            raise DraconicSyntaxError(SyntaxError("Loop control outside loop",
                                                  ("<string>", 1, 1, expr)))

    def execute(self, expr):
        """
        Executes an AST body.

        :type expr: str or list[ast.AST]
        """
        if not isinstance(expr, list):
            expr = self.parse(expr)

        self._preflight()
        try:
            self._exec(expr)
        except self._Return as r:
            return r.value
        except (self._Break, self._Continue):
            raise DraconicSyntaxError(SyntaxError("Loop control outside loop",
                                                  ("<string>", 1, 1, expr)))

    def _preflight(self):
        self._num_stmts = 0
        self._loops = 0
        super()._preflight()

    def _eval(self, node):
        self._num_stmts += 1
        if self._num_stmts > self._config.max_statements:
            raise TooManyStatements("You are trying to execute too many statements.", node)

        val = super()._eval(node)
        # ensure that it's always an instance of our safe compound types being returned
        # note: makes a copy, so the original copy won't be updated
        # we don't use isinstance because we're looking for very specific classes
        if type(val) is list:
            return self._list(val)
        elif type(val) is dict:
            return self._dict(val)
        elif type(val) is set:
            return self._set(val)
        return val

    def _exec(self, body):
        for expression in body:
            self._eval(expression)

    @property
    def names(self):
        return {**self.builtins, **self._names}

    @names.setter
    def names(self, new_names):
        self._names = new_names

    # ===== compound types =====
    def _eval_dict(self, node):
        return self._dict((self._eval(k), self._eval(v)) for (k, v) in zip(node.keys, node.values))

    def _eval_tuple(self, node):
        return tuple(self._eval(x) for x in node.elts)

    def _eval_list(self, node):
        return self._list(self._eval(x) for x in node.elts)

    def _eval_set(self, node):
        return self._set(self._eval(x) for x in node.elts)

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

        def do_generator(gi=0):
            """
            For each generator, set the names used in the final emitted value/the next generator.
            Only the final generator (gi = len(comprehension_node.generator)-1) should emit the final values,
            since only then are all possible necessary values set in extra_names.
            """
            generator_node = comprehension_node.generators[gi]
            for i in self._eval(generator_node.iter):
                self._loops += 1
                if self._loops > self._config.max_loops:
                    raise IterableTooLong('Comprehension generates too many elements', comprehension_node)

                # set names
                recurse_targets(generator_node.target, i)

                if all(self._eval(iff) for iff in generator_node.ifs):
                    if len(comprehension_node.generators) > gi + 1:
                        # next generator
                        yield from do_generator(gi + 1)  # bubble up emitted values
                    else:
                        # emit values
                        yield do_value(comprehension_node)

        try:
            yield from do_generator()
        finally:
            self.nodes.update({ast.Name: previous_name_evaller})

    # ===== assignments =====
    def _eval_assign(self, node):
        for target in node.targets:  # a = b = 1
            self._assign(target, node.value)

    def _eval_augassign(self, node):
        self._aug_assign(node.target, node.op, node.value)

    def _eval_namedexpr(self, node):
        self._assign(node.target, node.value)
        return self._eval_name(node.target)

    def _assign(self, names, values):
        try:
            handler = self.assign_nodes[type(names)]
        except KeyError:
            raise FeatureNotAvailable("Assignment to {} is not allowed".format(type(names).__name__), names)
        return handler(names, values)

    def _aug_assign(self, target, oper, value):
        # transform a += 1 to a = a + 1, then we can use assign and eval
        new_value = ast.BinOp(left=target, op=oper, right=value)
        ast.copy_location(new_value, target)
        self._assign(target, new_value)

    def _assign_name(self, name, value):
        if name.id in self.builtins:
            raise DraconicValueError(f"{name.id} is already builtin (no shadow assignments).", name)
        value = self._eval(value)
        self._names[name.id] = value

    def _assign_subscript(self, name, value):
        container = self._eval(name.value)
        key = self._eval(name.slice)
        value = self._eval(value)
        container[key] = value  # no further evaluation needed, if container is in names it will update

    def _assign_unpack(self, names, values):
        def do_assign(target, value):
            if not isinstance(target, (ast.Tuple, ast.List)):
                self._assign(target, self._FinalValue(value=value))
            else:
                try:
                    value = list(iter(value))
                except TypeError:
                    raise DraconicValueError("Cannot unpack non-iterable {} object".format(type(value).__name__), names)
                if not len(target.elts) == len(value):
                    raise DraconicValueError(
                        "Unequal unpack: {} names, {} values".format(len(target.elts), len(value)), names)
                for t, v in zip(target.elts, value):
                    do_assign(t, v)

        values = self._eval(values)
        do_assign(names, values)

    # ===== execution =====
    def _exec_return(self, node):
        raise self._Return(self._eval(node.value))

    def _exec_if(self, node):
        test = self._eval(node.test)
        if test:
            self._exec(node.body)
        else:
            self._exec(node.orelse)

    def _exec_for(self, node):
        for item in self._eval(node.iter):
            self._loops += 1
            if self._loops > self._config.max_loops:
                raise TooManyStatements('Too many loops (in for block)', node)

            self._assign(node.target, self._FinalValue(value=item))
            try:
                self._exec(node.body)
            except self._Break:
                break
            except self._Continue:
                continue
        else:
            self._exec(node.orelse)

    def _exec_while(self, node):
        while self._eval(node.test):
            self._loops += 1
            if self._loops > self._config.max_loops:
                raise TooManyStatements('Too many loops (in while block)', node)

            try:
                self._exec(node.body)
            except self._Break:
                break
            except self._Continue:
                continue
        else:
            self._exec(node.orelse)

    def _exec_break(self, node):
        raise self._Break

    def _exec_continue(self, node):
        raise self._Continue
