import pytest

from draconic import DraconicInterpreter
from draconic.exceptions import *
from draconic.helpers import DraconicConfig
from . import utils


@pytest.fixture()
def i():
    # 1000-size iterables, don't limit us by loops, signed 32b int limit
    config = DraconicConfig(max_loops=99999999, max_const_len=1000, max_int_size=32)
    return DraconicInterpreter(config=config)


# ==== explody things ====
def test_center(e):
    assert e("'foo'.center(5)") == ' foo '
    with utils.raises(IterableTooLong):
        e("'foo'.center(999999999999)")


def test_encode(e):
    with utils.raises(FeatureNotAvailable):
        e("'blargh'.encode()")

    with utils.raises(FeatureNotAvailable):
        e("b'blargh'")


def test_expandtabs(e):
    assert e("'\tfoo'.expandtabs()") == '\tfoo'.expandtabs()
    with utils.raises(IterableTooLong):
        e("'\tfoo'.expandtabs(99999999999)")
    with utils.raises(IterableTooLong):
        e("('\t'*999).expandtabs(2)")


def test_format(e):
    with utils.raises(FeatureNotAvailable):
        e("'{}'.format(1)")


def test_format_map(e):
    with utils.raises(FeatureNotAvailable):
        e("'{a}'.format_map({'a': 1})")


def test_join(e):
    assert e("'foo'.join('bar')") == 'bfooafoor'
    assert e("'foo'.join(['b', 'a', 'r'])") == 'bfooafoor'
    with utils.raises(AnnotatedException, match='expected str instance, int found'):
        e("'foo'.join([1, 2, 3])")
    with utils.raises(IterableTooLong):
        e("(' ' * 999).join(' ' * 999)")


def test_ljust(e):
    assert e("'foo'.ljust(5)") == "foo  "
    with utils.raises(IterableTooLong):
        e("'foo'.ljust(1001)")


def test_replace(e):
    assert e("'foo'.replace('o', 'a')") == 'faa'
    assert e("'foo'.replace('o', 'a', 1)") == 'fao'
    assert e("'foo'.replace('z', 'a'*999)") == 'foo'
    assert e("'foo'.replace('f', 'a'*998)") == 'foo'.replace('f', 'a' * 998)
    with utils.raises(IterableTooLong):
        e("'foo'.replace('o', 'a'*999)")
    with utils.raises(IterableTooLong):
        e("'foo'.replace('f', 'a'*999)")


def test_rjust(e):
    assert e("'foo'.rjust(5)") == '  foo'
    with utils.raises(IterableTooLong):
        e("'foo'.rjust(1001)")


def test_translate(e):
    assert e("'foo'.translate({102: 'ba', 111: 'na'})") == 'banana'
    with utils.raises(IterableTooLong):
        e("'ff'.translate({102: 'a'*999})")


def test_zfill(e):
    assert e("'15'.zfill(5)") == '00015'
    assert e("'-15'.zfill(5)") == '-0015'
    with utils.raises(IterableTooLong):
        e("'foo'.zfill(1001)")
    with utils.raises(IterableTooLong):
        e("'1'.zfill(1001)")
    with utils.raises(IterableTooLong):
        e("'-1'.zfill(1001)")


def test_fstring_limits(i, e):
    i.builtins.update({"a": 'foobar', "b": 42, "c": 3.14})
    assert e("f'{a} {b} {c}'") == 'foobar 42 3.14'

    assert e("f'{a:10}'") == 'foobar    '
    with utils.raises(IterableTooLong):
        e("f'{a:1001}'")

    assert e("f'{b:.10f}'") == '42.0000000000'
    with utils.raises(IterableTooLong):
        e("f'{b:.1001f}'")

    assert e("f'{c:.10f}'") == '3.1400000000'
    with utils.raises(IterableTooLong):
        e("f'{c:.1001f}'")

    assert e("f'{c:10.10f}'") == '3.1400000000'
    with utils.raises(IterableTooLong):
        e("f'{c:500.501f}'")

    with utils.raises(AnnotatedException, match="Invalid format specifier"):
        e("f'{c:foobar}'")


def test_printf_templating_limits(i, e):
    i.builtins.update({"a": 'foobar', "b": 42, "c": 3.14})
    assert e("'%s %d %f' % (a, b, c)") == '%s %d %f' % ('foobar', 42, 3.14)

    with utils.raises(IterableTooLong):
        e("'%(foo)s %(foo)s' % {'foo': 'a'*500}")

    assert e("'%10s' % a") == '    foobar'
    with utils.raises(IterableTooLong):
        e("'%1001s' % a")
    with utils.raises(IterableTooLong):
        e("'%1001d' % b")

    assert e("'%.10f' % b") == '42.0000000000'
    with utils.raises(IterableTooLong):
        e("'%.1001f' % b")

    assert e("'%.10f' % c") == '3.1400000000'
    with utils.raises(IterableTooLong):
        e("'%.1001f' % c")

    with utils.raises(FeatureNotAvailable):
        e("'%*f' % (a, b)")
    with utils.raises(FeatureNotAvailable):
        e("'%.*f' % (a, b)")
    with utils.raises(FeatureNotAvailable):
        e("'%*.*f' % (a, b, b)")


def test_printf_templating_edges(e):
    with utils.raises(AnnotatedException, match="format requires a mapping"):
        e("'%(foo)s' % 0")

    with utils.raises(AnnotatedException, match="'foo'"):
        e("'%(foo)s' % {}")

    with utils.raises(AnnotatedException, match="not enough arguments for format string"):
        e("'%s %s' % 0")

    with utils.raises(AnnotatedException, match="not enough arguments for format string"):
        e("'%s %s' % [0]")

    with utils.raises(AnnotatedException, match="format requires a mapping"):
        e("'%s %(foo)s' % 0")

    assert e("'%s %(foo)s' % {'foo': 0}") == "{'foo': 0} 0"
    with utils.raises(AnnotatedException, match="not enough arguments for format string"):
        e("'%(foo)s %s' % {'foo': 0}")

    assert e("'%%(foo)s %s' % {'foo': 0}") == "%(foo)s {'foo': 0}"  # this was actually a typo, but it's a good test


# ==== correctness ====
def test_getattr(i, e):
    """Check that our weird type shenanigans haven't borked anything when getattring w/ str key"""
    i.builtins.update(
        {
            "d": {"abc": "abc", 123: 123, ("1", 1): ("1", 1)},
            "l": [1, 2, "3"]
        }
        )
    assert e("d['abc']") == 'abc'
    assert e("d[123]") == 123
    assert e("d[('1', 1)]") == ("1", 1)

    assert e("l[0]") == 1
    assert e("l[-1]") == '3'

    assert e("({'a': 1}).a") == 1  # dot notation getattr


def test_strip(e):
    assert e("''.strip('')") == ''
    assert e("' aaa  '.strip()") == 'aaa'
    assert e("'foobar'.lstrip('f')") == 'oobar'
    assert e("'foobar'.rstrip('ra')") == 'foob'
