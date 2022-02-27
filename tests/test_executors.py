import pytest

from draconic.exceptions import *


def test_if_else(i, ex):
    expr = """
    if 1 < 0:
        print("true")
    else:
        print("false")
    """

    assert ex(expr) is None
    assert i.out__ == ["false"]


def test_for(i, ex):
    expr = """
    for i in range(5):
        print(i)
    print(i)
    """

    assert ex(expr) is None
    assert i.out__ == [0, 1, 2, 3, 4, 4]


def test_nested(i, ex):
    expr = """
    for i in range(5):
        if i < 2:
            print(f"{i} < 2")
        elif i == 2:
            print(f"{i} == 2")
        else:
            print(f"{i} > 2")
    """
    assert ex(expr) is None
    assert i.out__ == ["0 < 2", "1 < 2", "2 == 2", "3 > 2", "4 > 2"]


def test_nested_2(ex):
    expr = """
    total = 0
    x = 0
    while x < 2:
        y = 0
        while y < 2:
            y += 1
            total += 1
        x += 1
    return total
    """
    assert ex(expr) == 4


def test_keywords(i, ex):
    expr = """
    for i in range(10):
        if i < 5:
            continue
        print(i)
        if i == 7:
            break
    return i
    """
    assert ex(expr) == 7
    assert i.out__ == [5, 6, 7]

    expr = """
    i = 0
    while True:
        i += 1
        if i < 5:
            continue
        print(i)
        if i == 7:
            break
    return i
    """
    assert ex(expr) == 7
    assert i.out__ == [5, 6, 7]


def test_namedexpr_if(i, ex):
    expr = """
    if (a := 'true'):
        print(a)
    else:
        print('false')
    """

    assert ex(expr) is None
    assert i.out__ == ['true']


def test_namedexpr_for(i, ex):
    expr = """
    for i in (l := [1, 2, 3]):
        print(l.index(i))
    """

    assert ex(expr) is None
    assert i.out__ == [0, 1, 2]


def test_namedexpr_while(i, ex):
    expr = """
    i = 1
    while (a := i % 5) != 0:
        print(a)
        i += 1
    """

    assert ex(expr) is None
    assert i.out__ == [1, 2, 3, 4]


def test_infinite_loops(ex):
    expr = """
    while 1:
        pass
    """
    with pytest.raises(TooManyStatements):
        ex(expr)

    expr = """
    i = 0
    while i < 1000000000000000:
        i += 1
    """
    with pytest.raises(TooManyStatements):
        ex(expr)


# todo: test flow keywords in for loops and outside control flow
def test_break(ex):
    expr = """
    while 1:
        break
    return 1
    """
    assert ex(expr) == 1

    expr = """
    i = 0
    while i < 1000000000000000:
        i += 1
        if i == 5:
            break
    return i
    """
    assert ex(expr) == 5


def test_continue(ex):
    expr = """
    i = 0
    while 1:
        i += 1
        if i < 5:
            continue
        return i
    """
    assert ex(expr) == 5


def test_return(ex):
    expr = """
    while 1:
        return 1
    """
    assert ex(expr) == 1

    expr = """
    i = 0
    while i < 1000000000000000:
        i += 1
        if i == 5:
            return i
    """
    assert ex(expr) == 5
