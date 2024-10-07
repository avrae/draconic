import ast
import operator as op
from typing import Sequence

from .exceptions import *
from .types import *

__all__ = ("DraconicConfig", "OperatorMixin", "zip_star")

# ===== config =====
DISALLOW_PREFIXES = ["_", "func_"]
DISALLOW_METHODS = ["format", "format_map", "mro", "tb_frame", "gi_frame", "ag_frame", "cr_frame", "exec"]


class DraconicConfig:
    """A configuration object to pass into the Draconic interpreter."""

    def __init__(
        self,
        max_const_len=200_000,
        max_loops=10_000,
        max_statements=100_000,
        max_power_base=1_000_000,
        max_power=1_000,
        disallow_prefixes=None,
        disallow_methods=None,
        default_names=None,
        builtins_extend_default=True,
        max_int_size=64,
        max_recursion_depth=50,
    ):
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
        :param int max_int_size: The maximum allowed size of integers (-2^(pow-1) to 2^(pow-1)-1). Default 64.
                                 Integers can technically reach up to double this size before size check.
                                 *Not* the max value!
        :param int max_recursion_depth: The maximum allowed recursion depth.
        """
        if disallow_prefixes is None:
            disallow_prefixes = DISALLOW_PREFIXES
        if disallow_methods is None:
            disallow_methods = DISALLOW_METHODS

        self.max_const_len = max_const_len
        self.max_loops = max_loops
        self.max_statements = max_statements
        self.max_power_base = max_power_base
        self.max_power = max_power
        self.max_int_size = max_int_size
        self.min_int = -(2 ** (max_int_size - 1))
        self.max_int = (2 ** (max_int_size - 1)) - 1
        self.disallow_prefixes = disallow_prefixes
        self.disallow_methods = disallow_methods
        self.builtins_extend_default = builtins_extend_default
        self.max_recursion_depth = max_recursion_depth

        # types
        self._list = safe_list(self)
        self._dict = safe_dict(self)
        self._set = safe_set(self)
        self._str = safe_str(self)

        # default names
        if default_names is None:
            default_names = self._default_names()
        self.default_names = default_names

    @property
    def list(self):
        return self._list

    @property
    def dict(self):
        return self._dict

    @property
    def set(self):
        return self._set

    @property
    def str(self):
        return self._str

    def _default_names(self):
        return {
            "True": True,
            "False": False,
            "None": None,
            # functions
            "bool": bool,
            "int": int,
            "float": float,
            "str": self.str,
            "tuple": tuple,
            "dict": self.dict,
            "list": self.list,
            "set": self.set,
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
            ast.Sub: self._safe_sub,
            ast.Mult: self._safe_mult,
            ast.Div: op.truediv,
            ast.FloorDiv: op.floordiv,
            ast.Pow: self._safe_power,
            ast.Mod: op.mod,
            ast.LShift: self._safe_lshift,
            ast.RShift: op.rshift,
            ast.BitOr: op.or_,
            ast.BitXor: op.xor,
            ast.BitAnd: op.and_,
            ast.Invert: op.invert,
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
            _raise_in_context(NumberTooHigh, f"{a} ** {b} is too large of an exponent")
        result = a**b
        if isinstance(result, int) and (result < self._config.min_int or result > self._config.max_int):
            _raise_in_context(NumberTooHigh, "This exponent would create a number too large")
        return result

    def _safe_mult(self, a, b):
        """Multiplication: limit the size of iterables that can be created, and the max size of ints"""
        # sequences can only be multiplied by ints, so this is safe
        self._check_binop_operands(a, b)
        if isinstance(b, int) and b * approx_len_of(a) > self._config.max_const_len:
            _raise_in_context(IterableTooLong, "Multiplying these two would create something too long")
        if isinstance(a, int) and a * approx_len_of(b) > self._config.max_const_len:
            _raise_in_context(IterableTooLong, "Multiplying these two would create something too long")
        result = a * b
        if isinstance(result, int) and (result < self._config.min_int or result > self._config.max_int):
            _raise_in_context(NumberTooHigh, "Multiplying these two would create a number too large")
        return result

    def _safe_add(self, a, b):
        """Addition: limit the size of iterables that can be created, and the max size of ints"""
        self._check_binop_operands(a, b)
        if approx_len_of(a) + approx_len_of(b) > self._config.max_const_len:
            _raise_in_context(IterableTooLong, "Adding these two would create something too long")
        result = a + b
        if isinstance(result, int) and (result < self._config.min_int or result > self._config.max_int):
            _raise_in_context(NumberTooHigh, "Adding these two would create a number too large")
        return result

    def _safe_sub(self, a, b):
        """Addition: limit the max size of ints"""
        self._check_binop_operands(a, b)
        result = a - b
        if isinstance(result, int) and (result < self._config.min_int or result > self._config.max_int):
            _raise_in_context(NumberTooHigh, "Subtracting these two would create a number too large")
        return result

    def _safe_lshift(self, a, b):
        """Left Bit-Shift: limit the size of integers/floats to prevent CPU-locking computation"""
        self._check_binop_operands(a, b)

        if isinstance(b, int) and b > self._config.max_int_size - 2:
            _raise_in_context(NumberTooHigh, f"{a} << {b} is too large of a shift")

        result = a << b
        if isinstance(result, int) and (result < self._config.min_int or result > self._config.max_int):
            _raise_in_context(NumberTooHigh, "Shifting these two would create a number too large")

        return a << b

    def _check_binop_operands(self, a, b):
        """Ensures both operands of a binary operation are safe (int limit)."""
        if isinstance(a, int) and (a < self._config.min_int or a > self._config.max_int):
            _raise_in_context(NumberTooHigh, "This number is too large")
        if isinstance(b, int) and (b < self._config.min_int or b > self._config.max_int):
            _raise_in_context(NumberTooHigh, "This number is too large")


# ==== other utils ====
def zip_star(a: Sequence, b: Sequence, star_index: int):
    """
    Like zip(a, b), but zips the element at ``a[star_index]`` with a list of 0..len(b) elements such that every other
    element of ``a`` maps to exactly one element of ``b``.

    >>> zip_star(['a', 'b', 'c'], [1, 2, 3, 4], star_index=1)  # like a, *b, c = [1, 2, 3, 4]
    [('a', 1), ('b', [2, 3]), ('c', 4)]
    >>> zip_star(['a', 'b', 'c'], [1, 2], star_index=1)  # like a, *b, c = [1, 2]
    [('a', 1), ('b', []), ('c', 2)]

    Requires ``len(b) >= len(a) - 1`` and ``star_index < len(a)``.
    """
    if not 0 <= star_index < len(a):
        raise IndexError("'star_index' must be a valid index of 'a'")
    if not len(b) >= len(a) - 1:
        raise ValueError("'b' must be no more than 1 shorter than 'a'")

    length_difference = len(b) - (len(a) - 1)

    yield from zip(a[:star_index], b[:star_index])
    yield a[star_index], b[star_index : star_index + length_difference]
    yield from zip(a[star_index + 1 :], b[star_index + length_difference :])
