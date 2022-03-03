import pytest

from draconic import DraconicValueError


def test_bindings(i, ex):
    # stops executing on first match, name leaks to outer scope
    expr = """
    a = [1, 2, 3]
    match a:
        case [1, 2, x]:
            print(x)
        case x:
            print(x)
    print(x)
    """
    ex(expr)
    assert i.out__ == [3, 3]

    expr = """
    match a:
        case [x, *_]:
            print(x)
        case x:
            print(x)
    print(x)
    """
    ex(expr)
    assert i.out__ == [1, 1]

    expr = """
    match a:
        case [x, 1, 1]:
            print(x)
        case x:
            print(x)
    print(x)
    """
    ex(expr)
    assert i.out__ == [[1, 2, 3], [1, 2, 3]]

    # binding happens before guard execution
    expr = """
    match a:
        case [x, 2, 3] if x == 2:
            print(x)
        case y:
            print(y)
    print(x)
    """
    ex(expr)
    assert i.out__ == [[1, 2, 3], 1]

    # name aliases generate an *additional* binding
    expr = """
    a = [1, 2, 3]
    match a:
        case [x as y, 2, 3]:
            pass
    print(x)
    print(y)
    """
    ex(expr)
    assert i.out__ == [1, 1]

    expr = """
    match a:
        case [((b as c) as d) as e, 2, 3]:
            pass
    return b, c, d, e
    """
    assert ex(expr) == (1, 1, 1, 1)


def test_multiple_assignments(i, ex):
    # multiple assignments in same pattern
    expr = """
    a = [1, 2, 3]
    match a:
        case [x, x, x]:
            print(x)
    """
    with pytest.raises(DraconicValueError, match="multiple assignment"):
        ex(expr)

    # recursive too
    expr = """
    a = [1, [2]]
    match a:
        case [x, [x]]:
            print(x)
    """
    with pytest.raises(DraconicValueError, match="multiple assignment"):
        ex(expr)
