import contextlib

from draconic import DraconicConfig
from draconic.helpers import OperatorMixin


# noinspection PyProtectedMember
@contextlib.contextmanager
def temp_limits(interpreter: OperatorMixin, **limits):
    old_config = interpreter._config
    interpreter._config = DraconicConfig(**limits)
    yield
    interpreter._config = old_config
