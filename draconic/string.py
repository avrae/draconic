"""String utilities for the userstring type."""
import re

__all__ = (
    'FORMAT_SPEC_RE', 'JoinProxy', 'TranslateTableProxy'
)

# ==== format spec ====
# https://docs.python.org/3/library/string.html#format-specification-mini-language
_FILL = r"."
_ALIGN = r"[<>=^]"
_SIGN = r"[+\- ]"
_WIDTH = r"\d+"
_GROUPING_OPTION = r"[_,]"
_PRECISION = r"\d+"
_TYPE = r"[bcdeEfFgGnosxX%]"
FORMAT_SPEC_RE = re.compile(rf"((?P<fill>{_FILL})?(?P<align>{_ALIGN}))?"
                            rf"(?P<sign>{_SIGN})?"
                            rf"(?P<alt_form>#)?"
                            rf"(?P<zero_pad>0)?"
                            rf"(?P<width>{_WIDTH})?"
                            rf"(?P<grouping_option>{_GROUPING_OPTION})?"
                            rf"(?P<precision>\.{_PRECISION})?"
                            rf"(?P<type>{_TYPE})?")


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
