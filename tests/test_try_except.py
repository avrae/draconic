from draconic.exceptions import *
from . import utils


def test_try_except(i, ex):
    expr = """
    try:
        1/0
    except "Exception":
        return "I catch all exceptions!"
    except "ZeroDivisionError":
        return "You divided by zero!"
    """
    assert ex(expr) == "You divided by zero!"

    expr = """
    try:
        1/0
    except:
        return "I catch all exceptions!"
    except "ZeroDivisionError":
        return "You divided by zero!"
    """
    assert ex(expr) == "I catch all exceptions!"

    expr = """
    for x in ("foo", "None", "10e7", "10", "11"):
        try:
            print(int(x))
            break
        except "ValueError":
            print("NaN")
    """
    ex(expr)
    assert i.out__ == ["NaN", "NaN", "NaN", 10]

    expr = """
        for x in ("None", "10e7", "10", "11"):
            try:
                print(int(x))
                break
            except ("ValueError", "TypeError"):
                print("NaN")
        """
    ex(expr)
    assert i.out__ == ["NaN", "NaN", 10]

    expr = """
    def this_fails():
        x = 1/0
    
    try:
        this_fails()
    except "ZeroDivisionError":
        return "You divided by zero!"
    """
    assert ex(expr) == "You divided by zero!"


def test_except_as_not_allowed(ex):
    expr = """
    try:
        1/0
    except "ZeroDivisionError" as e:
        print(e)
    """
    with utils.raises(FeatureNotAvailable):
        ex(expr)


def test_try_else(i, ex):
    expr = """
    for divisor in (1, 0, 3, 0):
        try:
            print(1/divisor)
        except "ZeroDivisionError":
            print(">:c")
        else:
            print(":>")
    """
    ex(expr)
    assert i.out__ == [1, ":>", ">:c", 1 / 3, ":>", ">:c"]


def test_try_finally(i, ex):
    expr = """
    def divide(x, y):
        try:
            result = x / y
        except "ZeroDivisionError":
            print("division by zero!")
        else:
            print(f"result is {result}")
        finally:
            print("executing finally clause")
    
    divide(2, 1)
    divide(2, 0)
    divide("2", "1")
    """
    with utils.raises(TypeError):
        ex(expr)
    assert i.out__ == [
        "result is 2.0",
        "executing finally clause",
        "division by zero!",
        "executing finally clause",
        "executing finally clause",
    ]

    expr = """
    try:
        return True
    finally:
        return False
    """
    assert ex(expr) is False


def test_excepting_limits(i, ex):
    with utils.temp_limits(
        i,
        max_const_len=10,
        max_loops=10,
        max_statements=15,
        max_power_base=10,
        max_power=10,
        max_int_size=3,
        max_recursion_depth=3,
    ):
        with utils.raises(NumberTooHigh):
            ex(
                """
                try:
                    return 7 + 7
                except "NumberTooHigh":
                    pass
                """
            )

        with utils.raises(IterableTooLong):
            ex(
                """
                try:
                    return "aaaaaaaaaaa"
                except "IterableTooLong":
                    pass
                """
            )

        with utils.raises(TooManyStatements):
            ex(
                """
                try:
                    for _ in "123456789": pass
                    for _ in "123456789": pass
                except "TooManyStatements":
                    pass
                """
            )

        with utils.raises(TooMuchRecursion):
            ex(
                """
                def foo():
                    foo()
                
                try:
                    foo()
                except "TooMuchRecursion":
                    pass
                """
            )

        with utils.raises(NumberTooHigh):
            ex(
                """
                try:
                    return 7 + 7
                except:
                    pass
                """
            )


def test_incorrect_except_types(ex):
    expr = """
    try:
        1/0
    except None:
        pass
    """
    with utils.raises(FeatureNotAvailable):
        ex(expr)

    expr = """
    try:
        1/0
    except ["a", "b"]:
        pass
    """
    with utils.raises(FeatureNotAvailable):
        ex(expr)

    expr = """
    try:
        1/0
    except ("Exception", None):
        pass
    """
    with utils.raises(FeatureNotAvailable):
        ex(expr)


def test_try_except_flow_order(ex):
    expr = """
    try:
        return 0
    except:
        return 1
    else:
        return 2
    finally:
        return 3
    """
    assert ex(expr) == 3

    expr = """
    try:
        return 0
    except:
        return 1
    else:
        return 2
    """
    assert ex(expr) == 0

    expr = """
    try:
        return 0
    except:
        return 1
    finally:
        return 3
    """
    assert ex(expr) == 3

    expr = """
    try:
        return 0
    except:
        return 1
    """
    assert ex(expr) == 0

    expr = """
    try:
        return 0
    finally:
        return 3
    """
    assert ex(expr) == 3

    expr = """
    try:
        return 1/0
    except:
        return 1
    else:
        return 2
    finally:
        return 3
    """
    assert ex(expr) == 3

    expr = """
    try:
        return 1/0
    except:
        return 1
    else:
        return 2
    """
    assert ex(expr) == 1

    expr = """
    try:
        return 1/0
    except:
        return 1
    finally:
        return 3
    """
    assert ex(expr) == 3

    expr = """
    try:
        return 1/0
    except:
        return 1
    """
    assert ex(expr) == 1

    expr = """
    try:
        return 1/0
    finally:
        return 3
    """
    assert ex(expr) == 3
