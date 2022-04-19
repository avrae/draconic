import pytest

from draconic import DraconicValueError, FeatureNotAvailable
from draconic.versions import PY_310
from . import utils

pytestmark = pytest.mark.skipif(not PY_310, reason="requires python 3.10")


# many test cases taken from https://docs.python.org/3/whatsnew/3.10.html#pep-634-structural-pattern-matching

def test_match_literal(i, ex):
    expr = """
    for status in (400, 418, 403, "foo", []):
        match status:
            case 400:
                print("Bad request")
            case 404:
                print("Not found")
            case 418:
                print("I'm a teapot")
            case _:
                print("Something's wrong with the internet")
    """
    ex(expr)
    assert i.out__ == [
        "Bad request",
        "I'm a teapot",
        "Something's wrong with the internet",
        "Something's wrong with the internet",
        "Something's wrong with the internet"
    ]

    expr = """
    for status in (400, 418, 403, "foo", []):
        match status:
            case 400:
                print("Bad request")
            case 404:
                print("Not found")
            case 418:
                print("I'm a teapot")
            case 401 | 403 | 404:
                print("Not allowed")
            case _:
                print("Something's wrong with the internet")
    """
    ex(expr)
    assert i.out__ == [
        "Bad request",
        "I'm a teapot",
        "Not allowed",
        "Something's wrong with the internet",
        "Something's wrong with the internet"
    ]

    expr = """
    for status in (400, 418, 403, "foo", []):
        match status:
            case 400:
                print("Bad request")
            case 404:
                print("Not found")
            case 418:
                print("I'm a teapot")
    """
    ex(expr)
    assert i.out__ == [
        "Bad request",
        "I'm a teapot"
    ]


def test_literal_variable(i, ex):
    expr = """
    for point in [(0, 0), (0, 1), (1, 0), (1, 1), 123]:
        match point:
            case (0, 0):
                print("Origin")
            case (0, y):
                print(f"Y={y}")
            case (x, 0):
                print(f"X={x}")
            case (x, y):
                print(f"X={x}, Y={y}")
            case _:
                print("Not a point")
    """
    ex(expr)
    assert i.out__ == [
        "Origin",
        "Y=1",
        "X=1",
        "X=1, Y=1",
        "Not a point"
    ]


def test_nested_patterns(i, ex):
    expr = """
    for points in [
        [],
        [(0, 0)],
        [(0, 0), (0, 1)],
        [(1, 1)],
        [(0, 0), (1, 1)]
    ]:
        match points:
            case []:
                print("No points in the list.")
            case [(0, 0)]:
                print("The origin is the only point in the list.")
            case [(x, y)]:
                print(f"A single point {x}, {y} is in the list.")
            case [(0, y1), (0, y2)]:
                print(f"Two points on the Y axis at {y1}, {y2} are in the list.")
            case _:
                print("Something else is found in the list.")
    """
    ex(expr)
    assert i.out__ == [
        "No points in the list.",
        "The origin is the only point in the list.",
        "Two points on the Y axis at 0, 1 are in the list.",
        "A single point 1, 1 is in the list.",
        "Something else is found in the list."
    ]


def test_complex_wildcard(i, ex):
    expr = """
    for test_variable in [
        ('foo', 'bar', 'bletch'),
        ('warning', 100, 40),
        ('error', 404, 'foobar'),
        ('warning', 100, 100)
    ]:
        match test_variable:
            case ('warning', code, 40):
                print("A warning has been received.")
            case ('error', code, _):
                print(f"An error {code} occurred.")
    """
    ex(expr)
    assert i.out__ == [
        "A warning has been received.",
        "An error 404 occurred."
    ]


def test_guard(i, ex):
    expr = """
    for point in [(0, 0), (-1, 1), (-1, -1)]:
        match point:
            case (x, y) if x == y:
                print(f"The point is located on the diagonal Y=X at {x}.")
            case (x, y):
                print(f"Point is not on the diagonal.")
    """
    ex(expr)
    assert i.out__ == [
        "The point is located on the diagonal Y=X at 0.",
        "Point is not on the diagonal.",
        "The point is located on the diagonal Y=X at -1."
    ]


def test_sequence_pattern(i, ex):
    expr = """
    for nums in [
        [0, 0],
        [0, 1, 0],
        [0, 1, 2, 0],
        [0, 1],
        [1, 0],
        [1, 1],
        []
    ]:
        match nums:
            case [0, *middle, 0]:
                print(f"starts and ends at 0, middle={middle}")
            case [0, *middle]:
                print(f"starts at 0, middle={middle}")
            case [*middle, 0]:
                print(f"ends at 0, middle={middle}")
            case [1, *_]:
                print("starts at 1, we don't care about the rest")
    """
    ex(expr)
    assert i.out__ == [
        "starts and ends at 0, middle=[]",
        "starts and ends at 0, middle=[1]",
        "starts and ends at 0, middle=[1, 2]",
        "starts at 0, middle=[1]",
        "ends at 0, middle=[1]",
        "starts at 1, we don't care about the rest"
    ]


def test_sequence_muliple_starred(ex):
    # multiple starred names
    expr = """
    match [1, 2, 3]:
        case [*a, *a]:
            pass
    """
    with utils.raises(DraconicValueError, match="multiple starred names"):
        ex(expr)


def test_sequence_multiple_assignment(ex):
    # multiple assignments in same pattern
    expr = """
    a = [1, 2, 3]
    match a:
        case [x, x, x]:
            print(x)
    """
    with utils.raises(DraconicValueError, match="multiple assignment"):
        ex(expr)

    # recursive too
    expr = """
    a = [1, [2]]
    match a:
        case [x, [x]]:
            print(x)
    """
    with utils.raises(DraconicValueError, match="multiple assignment"):
        ex(expr)


def test_mapping_pattern(i, ex):
    expr = """
    for action in [
        {"color": "blue", "text": "hello world"},
        {"text": "ignore me!", "sleep": 2},
        {"sound": "beep", "format": "ogg"},
        {"sound": "boop", "format": "wav"},
        {"log": "thing", "a": 1, "foo": ["bar"]}
    ]:
        match action:
            case {"text": message, "color": c}:
                print(f"{c}: {message}")
            case {"sleep": duration}:
                print("z" * duration)
            case {"sound": url, "format": "ogg"}:
                print(f"playing {url}.ogg")
            case {"sound": _, "format": _}:
                print("Unsupported audio format")
            case {"log": logger, **rest}:
                print(f"LOG[{logger}]: {rest}")
    """
    ex(expr)
    assert i.out__ == [
        "blue: hello world",
        "zz",
        "playing beep.ogg",
        "Unsupported audio format",
        "LOG[thing]: {'a': 1, 'foo': ['bar']}"
    ]


def test_mapping_multiple_assignment(ex):
    expr = """
    match {1: 1, 2: 2}:
        case {1: a, 2: a}:
            pass
    """
    with utils.raises(DraconicValueError, match="multiple assignment"):
        ex(expr)

    expr = """
    match {1: 1, 2: 2}:
        case {1: a, **a}:
            pass
    """
    with utils.raises(DraconicValueError, match="multiple assignment"):
        ex(expr)


def test_match_singleton(i, ex):
    expr = """
    for value in [
        ("success", True),
        ("failure", False)
    ]:
        match value:
            case (val, True):
                print(f"success: {val}")
            case (val, False):
                print(f"failure: {val}")
    """
    ex(expr)
    assert i.out__ == [
        "success: success",
        "failure: failure"
    ]


def test_match_not_allowed(ex):
    expr = """
    match "foo":
        case str(val):
            print(val)
    """
    with utils.raises(FeatureNotAvailable):
        ex(expr)


def test_match_as(i, ex):
    expr = """
    for command in [
        "go north",
        "go south",
        "go up"
    ]:
        match command.split():
            case ["go", ("north" | "south" | "east" | "west") as direction]:
                print(f"Going {direction}!")
            case ["go", _]:
                print("I don't know how to go that way.")
    """
    ex(expr)
    assert i.out__ == [
        "Going north!",
        "Going south!",
        "I don't know how to go that way."
    ]


def test_binding_leaks(i, ex):
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
    a = [1, 2, 3]
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
    a = [1, 2, 3]
    match a:
        case [x, 1, 1]:
            print(x)
        case x:
            print(x)
    print(x)
    """
    ex(expr)
    assert i.out__ == [[1, 2, 3], [1, 2, 3]]


def test_binding_before_guard(i, ex):
    # binding happens before guard execution
    expr = """
    a = [1, 2, 3]
    match a:
        case [x, 2, 3] if x == 2:
            print(x)
        case y:
            print(y)
    print(x)
    """
    ex(expr)
    assert i.out__ == [[1, 2, 3], 1]


def test_binding_from_aliases(i, ex):
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
    a = [1, 2, 3]
    match a:
        case [((b as c) as d) as e, 2, 3]:
            pass
    return b, c, d, e
    """
    assert ex(expr) == (1, 1, 1, 1)
