import ast
import operator as op
from collections import UserList

from .exceptions import *

__all__ = ("DraconicConfig", "OperatorMixin", "approx_len_of", "safe_dict", "safe_list", "safe_set")

# ===== config =====
DISALLOW_PREFIXES = ['_', 'func_']
DISALLOW_METHODS = ['format', 'format_map', 'mro']


class DraconicConfig:
    """A configuration object to pass into the Draconic interpreter."""

    def __init__(self, max_const_len=200000, max_loops=10000, max_statements=100000, max_power_base=1000000,
                 max_power=1000, disallow_prefixes=None, disallow_methods=None,
                 default_names=None, builtins_extend_default=True):
        """
        Configuration object for the Draconic interpreter.

        :param int max_const_len: The maximum length literal that should be allowed to be constructed.
        :param int max_loops: The maximum total number of loops allowed per execution.
        :param int max_statements: The maximum total number of statements allowed per execution.
        :param int max_power_base: The maximum power base (x in x ** y)
        :param int max_power: The maximum power (y in x ** y)
        :param list disallow_prefixes: A list of str - attributes starting with any of these will be inaccessible
        :param list disallow_methods: A list of str - methods named these will not be callable
        :param dict default_names: A dict of str: Any - default names in the runtime
        :param bool builtins_extend_default: If False, ``builtins`` to the interpreter overrides default names
        """
        if disallow_prefixes is None:
            disallow_prefixes = DISALLOW_PREFIXES
        if disallow_methods is None:
            disallow_methods = DISALLOW_METHODS
        if default_names is None:
            default_names = self._default_functions()

        self.max_const_len = max_const_len
        self.max_loops = max_loops
        self.max_statements = max_statements
        self.max_power_base = max_power_base
        self.max_power = max_power
        self.disallow_prefixes = disallow_prefixes
        self.disallow_methods = disallow_methods
        self.default_names = default_names
        self.builtins_extend_default = builtins_extend_default

    def _default_functions(self):
        return {
            "int": int, "float": float, "str": str, "tuple": tuple,
            "dict": safe_dict(self), "list": safe_list(self), "set": safe_set(self)
        }


# ===== operators =====
class OperatorMixin:
    """A mixin class to provide the operators."""

    def __init__(self, config):
        """
        :type config: draconic.helpers.DraconicConfig
        """
        self._config = config

        self.operators = {
            # binary
            ast.Add: self._safe_add,
            ast.Sub: op.sub,
            ast.Mult: self._safe_mult,
            ast.Div: op.truediv,
            ast.FloorDiv: op.floordiv,
            ast.Pow: self._safe_power,
            ast.Mod: op.mod,
            # unary
            ast.Not: op.not_,
            ast.USub: op.neg,
            ast.UAdd: op.pos,
            # comparison
            ast.Eq: op.eq,
            ast.NotEq: op.ne,
            ast.Gt: op.gt,
            ast.Lt: op.lt,
            ast.GtE: op.ge,
            ast.LtE: op.le,
            ast.In: lambda x, y: op.contains(y, x),
            ast.NotIn: lambda x, y: not op.contains(y, x),
            ast.Is: lambda x, y: x is y,
            ast.IsNot: lambda x, y: x is not y,
        }

    def _safe_power(self, a, b):
        """Exponent: limit power base and power to prevent CPU-locking computation"""
        if abs(a) > self._config.max_power_base or abs(b) > self._config.max_power:
            raise NumberTooHigh(f"{a} ** {b} is too large of an exponent")
        return a ** b

    def _safe_mult(self, a, b):
        """Multiplication: limit the size of iterables that can be created"""
        # sequences can only be multiplied by ints, so this is safe
        if isinstance(b, int) and b * approx_len_of(a) > self._config.max_const_len:
            raise IterableTooLong('Multiplying these two would create something too long')
        if isinstance(a, int) and a * approx_len_of(b) > self._config.max_const_len:
            raise IterableTooLong('Multiplying these two would create something too long')

        return a * b

    def _safe_add(self, a, b):
        """Addition: limit the size of iterables that can be created"""
        if approx_len_of(a) + approx_len_of(b) > self._config.max_const_len:
            raise IterableTooLong("Adding these two would create something too long")
        return a + b


def approx_len_of(obj, visited=None):
    """Gets the approximate size of an object (including recursive objects)."""
    if isinstance(obj, str):
        return len(obj)

    if visited is None:
        visited = [obj]

    size = op.length_hint(obj)

    if isinstance(obj, dict):
        obj = obj.items()

    try:
        for child in iter(obj):
            if child in visited:
                continue
            size += approx_len_of(child, visited)
            visited.append(child)
    except TypeError:  # object is not iterable
        pass

    return size


# ===== compound types =====
# each function is a function that returns a class based on Draconic config
# ... look, it works

def safe_list(config):
    class SafeList(UserList):  # extends UserList so that [x] * y returns a SafeList, not a list
        def append(self, obj):
            if approx_len_of(self) + 1 > config.max_const_len:
                raise IterableTooLong("This list is too long")
            super().append(obj)

        def extend(self, iterable):
            if approx_len_of(self) + approx_len_of(iterable) > config.max_const_len:
                raise IterableTooLong("This list is too long")
            super().extend(iterable)

    return SafeList


def safe_set(config):
    class SafeSet(set):
        def update(self, *s):
            if approx_len_of(self) + sum(approx_len_of(other) for other in s) > config.max_const_len:
                raise IterableTooLong("This set is too large")
            super().update(*s)

        def add(self, element):
            if approx_len_of(self) + 1 > config.max_const_len:
                raise IterableTooLong("This set is too large")
            super().add(element)

        def union(self, *s):
            if approx_len_of(self) + sum(approx_len_of(other) for other in s) > config.max_const_len:
                raise IterableTooLong("This set is too large")
            return SafeSet(super().union(*s))

    return SafeSet


def safe_dict(config):
    class SafeDict(dict):
        def update(self, other_dict=None, **kvs):
            if other_dict is None:
                other_dict = {}

            if approx_len_of(self) + approx_len_of(other_dict) + approx_len_of(kvs) > config.max_const_len:
                raise IterableTooLong("This dict is too large")

            super().update(other_dict, **kvs)

    return SafeDict
