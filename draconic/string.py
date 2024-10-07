"""String utilities for the userstring type."""

import re

from .exceptions import IterableTooLong, _raise_in_context

__all__ = ("check_format_spec", "FORMAT_SPEC_RE", "PRINTF_TEMPLATE_RE", "JoinProxy", "TranslateTableProxy")

# ==== format spec ====
# .format()-style
# https://docs.python.org/3/library/string.html#format-specification-mini-language
_FILL = r"."
_ALIGN = r"[<>=^]"
_SIGN = r"[+\- ]"
_WIDTH = r"\d+"
_GROUPING_OPTION = r"[_,]"
_PRECISION = r"\d+"
_TYPE = r"[bcdeEfFgGnosxX%]"
FORMAT_SPEC_RE = re.compile(
    rf"(?:(?P<fill>{_FILL})?(?P<align>{_ALIGN}))?"
    rf"(?P<sign>{_SIGN})?"
    rf"(?P<alt_form>#)?"
    rf"(?P<zero_pad>0)?"
    rf"(?P<width>{_WIDTH})?"
    rf"(?P<grouping_option>{_GROUPING_OPTION})?"
    rf"(?:\.(?P<precision>{_PRECISION}))?"
    rf"(?P<type>{_TYPE})?"
)


def check_format_spec(config, format_spec):
    # validate that the format string is safe
    match = FORMAT_SPEC_RE.match(format_spec)
    if not match:
        raise ValueError("Invalid format specifier")

    precision_len = 0
    w = match.group("width")
    p = match.group("precision")
    if w:
        precision_len += int(w)
    if p:
        precision_len += int(p)
    if precision_len > config.max_const_len:
        _raise_in_context(IterableTooLong, "This str is too large")


# printf-style
# https://docs.python.org/3/library/stdtypes.html#printf-style-string-formatting
_PF_MAPPING_KEY = r"[^)]*"  # any sequence of non-")"
_PF_CONVERSION_FLAGS = r"[#0\- +]"
_PF_WIDTH = r"\*|\d+"
_PF_PRECISION = r"\*|\d+"
_PF_LENGTH_MODIFIER = r"[hlL]"
_PF_TYPE = r"[diouxXeEfFgGcrsa%]"
PRINTF_TEMPLATE_RE = re.compile(
    rf"%"
    rf"(?:\((?P<mapping_key>{_PF_MAPPING_KEY})\))?"
    rf"(?P<conversion_flags>{_PF_CONVERSION_FLAGS})*"
    rf"(?P<width>{_PF_WIDTH})?"
    rf"(?:\.(?P<precision>{_PF_PRECISION}))?"
    rf"(?P<length_modifier>{_PF_LENGTH_MODIFIER})?"
    rf"(?P<type>{_PF_TYPE})"
)


# ==== helpers ====
class JoinProxy:
    """
    A helper to return the right types for str.join().
    If the sequence would return a userstring, returns it as a base str instead.
    """

    def __init__(self, str_type, seq):
        self._str_type = str_type
        self.seq = seq

    def __iter__(self):
        for item in self.seq:
            if isinstance(item, self._str_type):
                yield str(item)
            else:
                yield item


class TranslateTableProxy:
    """
    A helper to return the right types for str.translate().
    If the table would return a userstring, returns it as a base str instead.
    """

    def __init__(self, str_type, table):
        self._str_type = str_type
        self.table = table

    def __getitem__(self, item):
        out = self.table[item]
        if isinstance(out, self._str_type):  # translate() expects strictly a str type
            return str(out)
        return out
