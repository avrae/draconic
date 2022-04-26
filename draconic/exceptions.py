import abc
import ast

from .versions import PY_310

__all__ = (
    "DraconicException",
    "DraconicSyntaxError",
    "InvalidExpression",
    "NotDefined",
    "FeatureNotAvailable",
    "DraconicValueError",
    "LimitException",
    "NumberTooHigh",
    "IterableTooLong",
    "TooManyStatements",
    "TooMuchRecursion",
    "WrappedException",
    "AnnotatedException",
    "NestedException",
    "_PostponedRaise",
    "_raise_in_context",
)


class DraconicException(Exception):
    """Base exception for all exceptions in this library."""

    __drac_context__: str = None

    def __init__(self, msg):
        super().__init__(msg)
        self.msg = msg


class DraconicSyntaxError(DraconicException):
    """Bad syntax."""

    def __init__(self, original: SyntaxError, expr):
        super().__init__(original.msg)
        self.lineno = original.lineno
        self.offset = original.offset
        self.end_lineno = None
        self.end_offset = None
        self.expr = expr

        if PY_310:
            self.end_lineno = original.end_lineno
            self.end_offset = original.end_offset

    @classmethod
    def from_node(cls, node: ast.AST, msg: str, expr):
        if PY_310:
            inner = SyntaxError(
                msg, ("<string>", node.lineno, node.col_offset + 1, expr, node.end_lineno, node.end_col_offset + 1)
            )
        else:
            inner = SyntaxError(msg, ("<string>", node.lineno, node.col_offset + 1, expr))
        return cls(inner, expr)


class InvalidExpression(DraconicException):
    """Base exception for all exceptions during run-time."""

    def __init__(self, msg, node, expr):
        super().__init__(msg)
        self.node = node
        self.expr = expr


class NotDefined(InvalidExpression):
    """Some name is not defined."""

    pass


class FeatureNotAvailable(InvalidExpression):
    """What you're trying to do is not allowed."""

    pass


class DraconicValueError(InvalidExpression):
    """Bad value passed to some function."""

    pass


class LimitException(InvalidExpression):
    """
    Something exceeded execution limits.
    """

    pass


class NumberTooHigh(LimitException):
    """Some number is way too big."""

    pass


class IterableTooLong(LimitException):
    """Some iterable is way too big."""

    pass


class TooManyStatements(LimitException):
    """Tried to execute too many statements."""

    pass


class TooMuchRecursion(LimitException):
    """Too deep in recursion."""

    pass


class WrappedException(InvalidExpression, abc.ABC):
    """abstract base exception for a lib exception that wraps some other exception"""

    original: BaseException


class AnnotatedException(WrappedException):
    """A wrapper for another exception to handle lineno info."""

    def __init__(self, original, node, expr):
        super().__init__(str(original), node, expr)
        self.original = original


class NestedException(WrappedException):
    """An exception occurred in a user-defined function call."""

    def __init__(self, msg, node, expr, last_exc):
        super().__init__(msg, node, expr)
        self.last_exc = last_exc  # type: DraconicException  # used for tracebacking
        # keep a reference to the end of the chain for easy comparison
        if isinstance(last_exc, WrappedException):
            self.original = last_exc.original
        else:
            self.original = last_exc


# we need to raise some exception, but don't have the node context right now
class _PostponedRaise(Exception):
    def __init__(self, cls, *args, **kwargs):
        self.cls = cls
        self.args = args
        self.kwargs = kwargs


def _raise_in_context(cls, *args, **kwargs):
    raise _PostponedRaise(cls, *args, **kwargs)
