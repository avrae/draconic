import ast
import operator as op

from .exceptions import *

__all__ = ("OperatorMixin",)


class OperatorMixin:
    """A mixin class to provide the operators."""

    def __init__(self, config):
        """
        :type config: draconic.config.DraconicConfig
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
        if hasattr(a, '__len__') and b * len(a) > self._config.max_const_len:
            raise IterableTooLong('Multiplying these two would create something too long')
        if hasattr(b, '__len__') and a * len(b) > self._config.max_const_len:
            raise IterableTooLong('Multiplying these two would create something too long')

        return a * b

    def _safe_add(self, a, b):
        """Addition: limit the size of iterables that can be created"""
        if hasattr(a, '__len__') and hasattr(b, '__len__'):
            if len(a) + len(b) > self._config.max_const_len:
                raise IterableTooLong("Adding these two would create something too long")
        return a + b
