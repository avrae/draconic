import contextlib

import pytest

from draconic import DraconicConfig
from draconic.exceptions import AnnotatedException, NestedException
from draconic.helpers import OperatorMixin


# noinspection PyProtectedMember
@contextlib.contextmanager
def temp_limits(interpreter: OperatorMixin, **limits):
    old_config = interpreter._config
    interpreter._config = DraconicConfig(**limits)
    yield
    interpreter._config = old_config


# since we have custom error handling with AnnotatedException and NestedException, we have to wrap
# pytest.raises() to account for situations where the actual expected exception is deep at the root of some expression
# chain
@contextlib.contextmanager
def raises(expected_exception, **kwargs):
    if isinstance(expected_exception, tuple):
        inner_expected = (*expected_exception, AnnotatedException, NestedException)
    else:
        inner_expected = (expected_exception, AnnotatedException, NestedException)

    with pytest.raises(inner_expected, **kwargs) as exc_info:
        yield

    # if we're here, the exception type is either the expected type or an unknown one of our wrappers

    # the exception type is exactly what we expected
    if issubclass(exc_info.type, expected_exception):
        return
    # the exception we care about is deeply nested or wrapped
    if (
        isinstance(exc_info.value, (AnnotatedException, NestedException))
        and expected_exception is not AnnotatedException
    ):
        assert isinstance(exc_info.value.original, expected_exception)
