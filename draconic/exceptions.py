__all__ = (
    "DraconicException", "DraconicSyntaxError",
    "InvalidExpression", "NotDefined", "FeatureNotAvailable", "DraconicValueError",
    "LimitException", "NumberTooHigh", "IterableTooLong", "TooManyStatements", "AnnotatedException",
    "_PostponedRaise", "_raise_in_context"
)


class DraconicException(Exception):
    """Base exception for all exceptions in this library."""
    pass


class DraconicSyntaxError(DraconicException):
    """Bad syntax."""

    def __init__(self, original: SyntaxError):
        super().__init__(original.msg)
        self.lineno = original.lineno
        self.offset = original.offset
        self.text = original.text


class InvalidExpression(DraconicException):
    """Base exception for all exceptions during run-time."""

    def __init__(self, msg, node):
        super().__init__(msg)
        self.node = node


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


class AnnotatedException(InvalidExpression):
    """A wrapper for another exception to handle lineno info."""

    def __init__(self, original, node):
        super().__init__(str(original), node)
        self.original = original


# we need to raise some exception, but don't have the node context right now
class _PostponedRaise(Exception):
    def __init__(self, cls, *args, **kwargs):
        self.cls = cls
        self.args = args
        self.kwargs = kwargs


def _raise_in_context(cls, *args, **kwargs):
    raise _PostponedRaise(cls, *args, **kwargs)
