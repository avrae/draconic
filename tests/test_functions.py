import math

import pytest

from draconic.exceptions import *


def test_basic_calls(ex):
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
    def test_args(a):
        pass
    return test_args(1, a=2)
    """
    with pytest.raises(AnnotatedException, match="got multiple values"):
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
    def test_args(a, *b, c):
        pass
    return test_args(1, 2)
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

    expr = """
    def fac(i):
        if i < 1:
            return 1
        return i*fac(i-1)
    return fac(20)
    """
    assert ex(expr) == math.factorial(20)

    expr = """
    def fac(i):
        if i < 1:
            return 1
        return i*fac(i-1)
    return fac(40)
    """
    with pytest.raises(NumberTooHigh):
        ex(expr)

    expr = """
    def fac(i):
        if i < 1:
            return 1
        return i*fac(i-1)
    return fac(50)
    """
    with pytest.raises(TooMuchRecursion):
        ex(expr)


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

    expr = """
    a = 1
    def incr_locally():
        a += 1
        return a
    return a, incr_locally(), incr_locally(), a
    """
    assert ex(expr) == (1, 2, 2, 1)  # NOTE: different from python 3.10, which raises UnboundLocalError


def test_bare_loop_control(ex):
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


def test_external_callers(i, ex):
    i._names['map'] = map

    expr = """
    def first(i):
        return i[0]
    
    def second(i):
        return i[1]
    
    a = [(0, 3), (1, 2), (2, 1), (3, 0)]
    return list(map(first, a)), list(map(second, a))
    """
    assert ex(expr) == ([0, 1, 2, 3], [3, 2, 1, 0])

    expr = """
    a = [(0, 3), (1, 2), (2, 1), (3, 0)]
    return list(map(lambda i: i[0], a)), list(map(lambda i: i[1], a))
    """
    assert ex(expr) == ([0, 1, 2, 3], [3, 2, 1, 0])


def test_pass_by_value(i, ex):
    i._names['foo'] = 1
    expr = """
    foo2 = 2
    
    def bar(target):
        target += 1
    
    bar(foo)
    bar(foo2)
    return foo, foo2
    """
    assert ex(expr) == (1, 2)


def test_pass_by_reference(i, ex):
    i._names['foo'] = [1, 2, 3]
    expr = """
    foo2 = [1, 2, 3]
    
    def bar(target):
        target.append(4)
    
    bar(foo)
    bar(foo2)
    return foo, foo2
    """
    assert ex(expr) == ([1, 2, 3], [1, 2, 3, 4])  # since true lists are immutable in our safe type system


def test_breakout_default(i, ex):
    class Foo:  # random class with a private attr
        _private = 1
        public = 2

    i._names['foo'] = Foo()

    expr = """
    def bar(baz=foo._private):
        return baz
        
    return bar()
    """
    with pytest.raises(FeatureNotAvailable):
        ex(expr)


def test_breakout_external_caller(i, ex):
    class Foo:
        _private = 1
        public = 2

    i._names['foo'] = Foo()
    i._names['map'] = map

    expr = """
    return list(map(lambda foo: foo._private, [foo]))
    """
    with pytest.raises(FeatureNotAvailable):
        ex(expr)


def test_function_naming(ex):
    expr = """
    def foo():
        pass
    
    bar = lambda: 0
    return str(foo), str(bar)
    """
    assert ex(expr) == ("<Function foo>", "<Function <lambda>>")


def test_shadow_assignment(i, ex):
    i.builtins["shadow"] = "spooky"
    expr = """
    def shadow():
        return "scary"
    """
    with pytest.raises(DraconicValueError):
        ex(expr)
