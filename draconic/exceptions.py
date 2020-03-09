__all__ = (
    "InvalidExpression", "NotDefined", "FeatureNotAvailable", "DraconicValueError", "LimitException", "NumberTooHigh",
    "IterableTooLong", "TooManyStatements"
)


class InvalidExpression(Exception):
    """Base exception for all Draconic exceptions."""
    pass


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
    """Something exceeded execution limits."""
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
