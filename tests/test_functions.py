import pytest

from draconic.exceptions import *


def test_functions(ex):
    expr = """
    def times2(i):
        return i*2
    return times2(5)
    """
    assert ex(expr) == 10

    expr = """
    def test_args(a, b, /, c, d=2, *args, e=None, **kwargs):
        return a, b, c, d, e, args, kwargs
    return test_args(1, 2, c=3, e='foo')
    """
    assert ex(expr) == (1, 2, 3, 2, 'foo', (), {})


def test_valid_args(ex):
    expr = """
    def test_args(a=1, /):
        return a
    return test_args(2)
    """
    assert ex(expr) == 2

    expr = """
    def test_args(a=1, /):
        return a
    return test_args()
    """
    assert ex(expr) == 1

    expr = """
    def test_args(a=1):
        return a
    return test_args()
    """
    assert ex(expr) == 1

    expr = """
    def test_args(a=1):
        return a
    return test_args(2)
    """
    assert ex(expr) == 2

    expr = """
    def test_args(a=1):
        return a
    return test_args(a=2)
    """
    assert ex(expr) == 2

    expr = """
    def test_args(*, a=1):
        return a
    return test_args()
    """
    assert ex(expr) == 1

    expr = """
    def test_args(*, a=1):
        return a
    return test_args(a=2)
    """
    assert ex(expr) == 2

    expr = """
    def test_args(*args, **kwargs):
        return args, kwargs
    return test_args(1, 2, 3, a=1, b=2)
    """
    assert ex(expr) == ((1, 2, 3), {'a': 1, 'b': 2})


def test_invalid_args(ex):
    expr = """
    def test_args(a, b, /, c, d=2, *args, e=None, **kwargs):
        return a, b, c, d, e, args, kwargs
    return test_args()
    """
    with pytest.raises(AnnotatedException, match="missing required positional argument"):
        ex(expr)

    expr = """
    def test_args(a):
        pass
    return test_args(1, 2)
    """
    with pytest.raises(AnnotatedException, match="2 were given"):
        ex(expr)

    expr = """
    def test_args(a, /, b):
        pass
    return test_args()
    """
    with pytest.raises(AnnotatedException, match="missing required positional argument"):
        ex(expr)

    expr = """
    def test_args(a, /, b):
        pass
    return test_args(1)
    """
    with pytest.raises(AnnotatedException, match="missing required positional argument"):
        ex(expr)

    expr = """
    def test_args(*, a):
        pass
    return test_args()
    """
    with pytest.raises(AnnotatedException, match="missing required keyword argument"):
        ex(expr)

    expr = """
    def test_args(*, a):
        pass
    return test_args(a=1, b=2)
    """
    with pytest.raises(AnnotatedException, match="got unexpected keyword arguments"):
        ex(expr)

    expr = """
    def test_args(a, /):
        pass
    return test_args(a=1)
    """
    # this should be "got some positional-only arguments passed as keyword arguments" but that's annoying
    # so it's missing required positional argument
    with pytest.raises(AnnotatedException, match="missing required positional argument"):
        ex(expr)


def test_recursion_factorial(ex):
    expr = """
    def fac(i):
        if i < 1:
            return 1
        return i*fac(i-1)
    return fac(5)
    """
    assert ex(expr) == 120


def test_recursion_limits(ex):
    expr = """
    def foo():
        foo()
    foo()
    """
    with pytest.raises(TooMuchRecursion):
        ex(expr)


def test_recursion_even_or_odd(ex):
    expr = """
    def is_even(i):
        if i == 2:
            return True
        elif i < 2:
            return False
        return is_odd(i-1)
        
    def is_odd(i):
        return is_even(i-1)
        
    return is_even(42), is_odd(42)
    """
    assert ex(expr) == (True, False)


def test_function_scoping(ex):
    expr = """
    def bar():
        return b

    def foo():
        b = 1
        return bar()

    return foo()
    """
    with pytest.raises(NotDefined):
        ex(expr)

    expr = """
    def foo():
        b = 1
        def bar():
            return b
        b = 2
        return bar()
    return foo()
    """
    assert ex(expr) == 2  # thanks, python

    expr = """
    a = 1
    def foo():
        return a
    a = 2
    return foo()
    """
    assert ex(expr) == 2  # thanks, python

    expr = """
    a = 2
    def foo():
        a = 1
        return a
    foo()
    return a
    """
    assert ex(expr) == 2

    expr = """
    a = 42
    
    def set_a_to_1():
        a = 1
        return a
        
    def set_a_to_2():
        a = 2
        return a
        
    def foo():
        a = 3
        return a, set_a_to_1(), set_a_to_2()
        
    foo()
    return a, foo(), set_a_to_1(), set_a_to_2()
    """
    assert ex(expr) == (42, (3, 1, 2), 1, 2)


def test_weird_edges(ex):
    expr = """
    def foo():
        break
    foo()
    """
    with pytest.raises(DraconicSyntaxError):
        ex(expr)

    expr = """
    def foo():
        continue
    foo()
    """
    with pytest.raises(DraconicSyntaxError):
        ex(expr)


def test_lambdas(ex):
    expr = """
    double = lambda x: x * 2
    return double(1), double(2)
    """
    assert ex(expr) == (2, 4)


def test_lambda_calculus(ex):
    # thanks, CSE 116 notes
    expr = """
    pair = lambda left, right: lambda b: left if b else right
    fst = lambda the_pair: the_pair(True)
    snd = lambda the_pair: the_pair(False)
    my_pair = pair(1, 2)
    return fst(my_pair), snd(my_pair)
    """
    assert ex(expr) == (1, 2)

    # church numerals
    expr = """
    zero = lambda f, x: x
    one = lambda f, x: f(x)
    incr = lambda n: lambda f, x: f(n(f, x))
    add1 = lambda x: x + 1
    return zero(add1, 0), one(add1, 0), incr(one)(add1, 0)
    """
    assert ex(expr) == (0, 1, 2)

    # church addition!
    expr = """
    zero = lambda f, x: x
    one = lambda f, x: f(x)
    incr = lambda n: lambda f, x: f(n(f, x))
    add = lambda n, m: n(incr, m)
    add1 = lambda x: x + 1
    two = add(one, one)
    return (add(one, one)(add1, 0),  # 1 + 1
            add(two, one)(add1, 0),  # 2 + 1
            add(add(two, one), add(two, one))(add1, 0))  # (2 + 1) + (2 + 1)
    """
    assert ex(expr) == (2, 3, 6)
