import pytest

from draconic import DraconicInterpreter
from draconic.exceptions import *
from draconic.helpers import DraconicConfig


@pytest.fixture()
def i():
    # 1000-size iterables, don't limit us by loops, signed 32b int limit
    config = DraconicConfig(max_loops=99999999, max_const_len=1000, max_int_size=32)
    return DraconicInterpreter(config=config)


def test_center(e):
    assert e("'foo'.center(5)") == ' foo '
    with pytest.raises(IterableTooLong):
        e("'foo'.center(999999999999)")


def test_encode(e):
    with pytest.raises(FeatureNotAvailable):
        e("'blargh'.encode()")

    with pytest.raises(FeatureNotAvailable):
        e("b'blargh'")


def test_expandtabs(e):
    assert e("'\tfoo'.expandtabs()") == '\tfoo'.expandtabs()
    with pytest.raises(IterableTooLong):
        e("'\tfoo'.expandtabs(99999999999)")
    with pytest.raises(IterableTooLong):
        e("('\t'*999).expandtabs(2)")


def test_format(e):
    with pytest.raises(FeatureNotAvailable):
        e("'{}'.format(1)")


def test_format_map(e):
    with pytest.raises(FeatureNotAvailable):
        e("'{a}'.format_map({'a': 1})")


def test_join(e):
    assert e("'foo'.join('bar')") == 'bfooafoor'
    assert e("'foo'.join(['b', 'a', 'r'])") == 'bfooafoor'
    with pytest.raises(AnnotatedException, match='expected str instance, int found'):
        e("'foo'.join([1, 2, 3])")
    with pytest.raises(IterableTooLong):
        e("(' ' * 999).join(' ' * 999)")


def test_ljust(e):
    assert e("'foo'.ljust(5)") == "foo  "
    with pytest.raises(IterableTooLong):
        e("'foo'.ljust(1001)")


def test_replace(e):
    assert e("'foo'.replace('o', 'a')") == 'faa'
    assert e("'foo'.replace('z', 'a'*999)") == 'foo'
    assert e("'foo'.replace('f', 'a'*998)") == 'foo'.replace('f', 'a' * 998)
    with pytest.raises(IterableTooLong):
        e("'foo'.replace('o', 'a'*999)")
    with pytest.raises(IterableTooLong):
        e("'foo'.replace('f', 'a'*999)")


def test_rjust(e):
    assert e("'foo'.rjust(5)") == '  foo'
    with pytest.raises(IterableTooLong):
        e("'foo'.rjust(1001)")


def test_translate(e):
    assert e("'foo'.translate({102: 'ba', 111: 'na'})") == 'banana'
    with pytest.raises(IterableTooLong):
        e("'ff'.translate({102: 'a'*999})")


def test_zfill(e):
    assert e("'15'.zfill(5)") == '00015'
    assert e("'-15'.zfill(5)") == '-0015'
    with pytest.raises(IterableTooLong):
        e("'foo'.zfill(1001)")
    with pytest.raises(IterableTooLong):
        e("'1'.zfill(1001)")
    with pytest.raises(IterableTooLong):
        e("'-1'.zfill(1001)")

