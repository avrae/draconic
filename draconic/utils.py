"""
This submodule contains helpful public utilities.
"""

import textwrap
from collections import namedtuple
from typing import List, Union

from .exceptions import AnnotatedException, DraconicException, DraconicSyntaxError, InvalidExpression, NestedException

LineInfo = namedtuple("LineInfo", "lineno col_offset end_lineno end_col_offset")


def format_traceback(exc: DraconicException) -> List[str]:
    """
    Given an exception raised by this library during execution of a userscript, provide a ``traceback``-like format
    of the call stack leading to the exception.
    """
    tb = ["Traceback (most recent call last):\n"]

    # show the call stack with pointers
    while isinstance(exc, NestedException):
        if exc.__drac_context__ is not None:
            tb.append(f"  Line {exc.node.lineno}, col {exc.node.col_offset}, in {exc.__drac_context__}\n")
        else:
            tb.append(f"  Line {exc.node.lineno}, col {exc.node.col_offset}\n")
        tb.append(textwrap.indent(format_exc_line_pointer(exc.node, exc.expr), "    "))

        exc = exc.last_exc

    # show the pointer to the original (draconic) exception
    in_func = f", in {exc.__drac_context__}" if exc.__drac_context__ is not None else ""
    if isinstance(exc, InvalidExpression):
        tb.append(f"  Line {exc.node.lineno}, col {exc.node.col_offset}{in_func}\n")
        tb.append(textwrap.indent(format_exc_line_pointer(extract_line_info(exc), exc.expr), "    "))
    elif isinstance(exc, DraconicSyntaxError):
        tb.append(f"  Line {exc.lineno}, col {exc.offset}{in_func}\n")
        tb.append(textwrap.indent(format_exc_line_pointer(extract_line_info(exc), exc.expr), "    "))
    else:  # pragma: no cover  # generic fallback, should never be hit
        tb.append(f"  While parsing expression{in_func}\n")

    # show the original exception message
    if isinstance(exc, AnnotatedException):
        exc = exc.original
    tb.append(f"{type(exc).__name__}: {exc!s}\n")
    return tb


def extract_line_info(exc: Union[InvalidExpression, DraconicSyntaxError]):
    if isinstance(exc, InvalidExpression):
        return LineInfo(
            exc.node.lineno,
            exc.node.col_offset,
            getattr(exc.node, "end_lineno", None),
            getattr(exc.node, "end_col_offset", None),
        )
    return LineInfo(
        exc.lineno,
        exc.offset - 1,
        exc.end_lineno,
        (exc.end_offset - 1) if exc.end_offset is not None else None,
    )


def format_exc_line_pointer(line_info: LineInfo, expr: str) -> str:
    the_line = expr.split("\n")[line_info.lineno - 1]

    # if the error spans multiple lines just point to the start
    if line_info.end_lineno is not None and line_info.end_lineno - line_info.lineno:
        return f"{the_line}\n{' ' * line_info.col_offset}^\n"

    # otherwise, if we have end_col_offset info, we need more than 1 carat
    if line_info.end_col_offset is not None:
        carats = "^" * (line_info.end_col_offset - line_info.col_offset)
    else:
        carats = "^"

    return textwrap.dedent(f"{the_line}\n{' ' * line_info.col_offset}{carats}\n")
