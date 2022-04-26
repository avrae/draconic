import re
import textwrap

import pytest

from draconic import DraconicException, utils
from draconic.versions import PY_310


# ==== helpers ====
def ex_with_exc(i, expr):
    with pytest.raises(DraconicException) as exc_info:
        i.execute(textwrap.dedent(expr))
    return "".join(utils.format_traceback(exc_info.value))


def tb_compare(result, expected):
    # prior to python 3.10, we didn't have the end_col info
    if PY_310:
        assert result == expected
    else:
        assert result == re.sub(r"\^+", "^", expected)


# ==== tests ====
# --- flat error ---
flat_exc_tb = """Traceback (most recent call last):
  Line 1, col 0
    1/0
    ^^^
ZeroDivisionError: division by zero
"""


def test_flat_exc(i):
    expr = "1/0"
    tb = ex_with_exc(i, expr)
    tb_compare(tb, flat_exc_tb)


# --- syntax error ---
syntax_error_tb1 = """Traceback (most recent call last):
  Line 1, col 9
    lambda: continue
            ^^^^^^^^
DraconicSyntaxError: invalid syntax
"""
syntax_error_tb2 = """Traceback (most recent call last):
  Line 8, col 0
    bar()
    ^^^^^
  Line 6, col 4, in bar
    foo()
    ^^^^^
  Line 3, col 5, in foo
    continue
    ^^^^^^^^
DraconicSyntaxError: Loop control outside loop
"""


def test_syntax_error(i):
    expr = "lambda: continue"
    tb = ex_with_exc(i, expr)
    tb_compare(tb, syntax_error_tb1)

    expr = """
    def foo():
        continue

    def bar():
        foo()

    bar()
    """
    tb = ex_with_exc(i, expr)
    tb_compare(tb, syntax_error_tb2)


# --- multiline syntax errors ---
multi_syntax_tb = """Traceback (most recent call last):
  Line 3, col 5
        a1 and 
        ^
DraconicSyntaxError: invalid syntax. Perhaps you forgot a comma?
"""


def test_multiline_syntax_error(i):
    expr = """
    (
        a1 and 
        a2 and
        a1 
        2 
        3 
        4
    )
    """
    tb = ex_with_exc(i, expr)
    tb_compare(tb, multi_syntax_tb)


# --- nested exception ---
nested_exc_tb = """Traceback (most recent call last):
  Line 8, col 0
    bar()
    ^^^^^
  Line 6, col 4, in bar
    foo()
    ^^^^^
  Line 3, col 4, in foo
    1/0
    ^^^
ZeroDivisionError: division by zero
"""


def test_nested_exc(i):
    expr = """
    def foo():
        1/0
    
    def bar():
        foo()
    
    bar()
    """
    tb = ex_with_exc(i, expr)
    tb_compare(tb, nested_exc_tb)


# --- exception in external caller ---
def faulty_code():
    return 1 / 0


def call_me(func):
    return func()


external_tb1 = """Traceback (most recent call last):
  Line 1, col 0
    faulty_code()
    ^^^^^^^^^^^^^
ZeroDivisionError: division by zero
"""
external_tb2 = """Traceback (most recent call last):
  Line 5, col 0
    call_me(foo)
    ^^^^^^^^^^^^
  Line 3, col 11, in foo
    return 1/0
           ^^^
ZeroDivisionError: division by zero
"""


def test_external_exc(i):
    i._names.update({"faulty_code": faulty_code, "call_me": call_me})
    tb = ex_with_exc(i, "faulty_code()")
    tb_compare(tb, external_tb1)

    expr = """
    def foo():
        return 1/0
    
    call_me(foo)
    """
    tb = ex_with_exc(i, expr)
    tb_compare(tb, external_tb2)
