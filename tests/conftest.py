import textwrap

import pytest

from draconic import DraconicInterpreter
from draconic.helpers import DraconicConfig


@pytest.fixture()
def i():
    config = DraconicConfig()
    inter = DraconicInterpreter(config=config)

    inter.out__ = []

    def foo(v):
        inter.out__.append(v)

    inter.builtins['print'] = foo
    inter.builtins['range'] = range
    return inter


@pytest.fixture()
def e(i):
    """eval"""
    def inner(expr):
        return i.eval(expr)

    return inner


# to really test functions, we parameterize every test with a bare expression and also with it wrapped in a function
# and lambda
def _ex_impl_bare(i, expr):
    return i.execute(expr)


def _ex_impl_func(i, expr):
    func_expr = (
        f"def PYTEST_IMPL_EX():\n"
        f"{textwrap.indent(expr, '    ')}\n"
        f"return PYTEST_IMPL_EX()"
    )
    return i.execute(func_expr)


@pytest.fixture(params=[_ex_impl_bare, _ex_impl_func], ids=["bare", "wrapped_func"])
def ex(i, request):
    """execute"""
    impl = request.param

    def inner(expr):
        i.out__ = []
        return impl(i, textwrap.dedent(expr))

    return inner


@pytest.fixture()
def exm(i):
    """execute module"""
    def inner(expr):
        return i.execute_module(expr)

    return inner
