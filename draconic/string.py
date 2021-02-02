"""String utilities for the userstring type."""
import re

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
