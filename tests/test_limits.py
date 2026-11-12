import pytest

from draconic import DraconicInterpreter
from draconic.exceptions import *
from draconic.helpers import DraconicConfig
from draconic.versions import PY_39
from tests.utils import temp_limits
from . import utils


@pytest.fixture()
def i():
    # 1000-size iterables, don't limit us by loops, signed 32b int limit
    config = DraconicConfig(max_loops=99999999, max_const_len=1000, max_int_size=32)
    return DraconicInterpreter(config=config)


def test_creating(i, e):
    really_long_str = "foo" * 1000
    not_quite_as_long = "f" * 999

    i._names["long"] = really_long_str
    i._names["lesslong"] = not_quite_as_long

    # strings
    with utils.raises(IterableTooLong):
        e(f"'{really_long_str}'")


def test_f_string(i, e):
    really_long_str = "foo" * 1000
    not_quite_as_long = "f" * 999
    i._names["long"] = really_long_str
    i._names["lesslong"] = not_quite_as_long

    assert e("lesslong") == not_quite_as_long
    assert e("f'{lesslong}'") == not_quite_as_long
    assert e("f'{lesslong}a'") == not_quite_as_long + "a"

    with utils.raises(IterableTooLong):
        e("f'{long}'")

    with utils.raises(IterableTooLong):
        e("f'{lesslong}{lesslong}'")

    with utils.raises(IterableTooLong):
        e("f'{lesslong}aaaaaa'")


def test_list(i, e):
    e("long = [1] * 1000")

    with utils.raises(IterableTooLong):
        e("long.append(1)")

    with utils.raises(IterableTooLong):
        e("long.extend([1])")

    with utils.raises(IterableTooLong):
        e("long.extend(long)")

    with utils.raises(IterableTooLong):
        e("[1, *long]")

    with utils.raises(IterableTooLong):
        e("[*long, *long]")

    # we should be able to unpack at the limit
    e("[*long]")

    # functions shouldn't be limited
    i.builtins["max"] = max
    e("max(*long, *long)")

    # we should always be operating using safe lists
    i.builtins["reallist"] = [1, 2, 3]
    e("my_list = [1, 2, 3]")
    assert isinstance(e("my_list + reallist"), i._list)
    assert isinstance(e("reallist + my_list"), i._list)
    e("my_list.extend(reallist)")
    assert isinstance(e("my_list"), i._list)

    # check that you can't bypass cont limits with comprehension
    i.builtins["range"] = range
    e("[f'{x:03}' for x in range(250)]")

    with utils.raises(IterableTooLong):
        e("[f'{x:03}' for x in range(251)]")


def test_set(i, e):
    i.builtins["range"] = range
    e("long = set(range(1000))")
    e("long2 = set(range(1000, 2000))")
    e("longer = set(range(1001))")

    with utils.raises(IterableTooLong):
        e("long.add(1000)")

    with utils.raises(IterableTooLong):
        e("long.update(long2)")

    with utils.raises(IterableTooLong):
        e("long.update({1000})")

    with utils.raises(IterableTooLong):
        e("long.union(long2)")

    with utils.raises(IterableTooLong):
        e("long | long2")

    with utils.raises(IterableTooLong):
        e("longer.intersection(longer)")

    with utils.raises(IterableTooLong):
        e("longer & longer")

    with utils.raises(IterableTooLong):
        e("long.symmetric_difference(long2)")

    with utils.raises(IterableTooLong):
        e("long ^ long2")

    with utils.raises(IterableTooLong):
        e("long |= long2")

    with utils.raises(IterableTooLong):
        e("longer &= longer")

    with utils.raises(IterableTooLong):
        e("longer.intersection_update(longer)")

    with utils.raises(IterableTooLong):
        e("long ^= long2")

    with utils.raises(IterableTooLong):
        e("long.symmetric_difference_update(long2)")

    with utils.raises(IterableTooLong):
        e("{*long, 1000}")

    with utils.raises(IterableTooLong):
        e("{*longer}")

    # we should be able to unpack at the limit
    e("{*long}")

    # we should always be operating using safe sets
    i.builtins["realset"] = {1, 2, 3}
    e("my_set = {3, 4, 5}")
    assert isinstance(e("my_set | realset"), i._set)
    assert isinstance(e("realset | my_set"), i._set)
    e("my_set.update(realset)")
    assert isinstance(e("my_set"), i._set)
    assert isinstance(e("my_set.union(realset)"), i._set)


def test_dict(i, e):
    i.builtins["range"] = range
    e("long = {f'{i:03}': 'a' for i in range(200)}")
    e("long2 = dict((f'{i:03}', 'a') for i in range(200, 342))")
    e("long_copy = long.copy()")

    with utils.raises(IterableTooLong):
        e("long.update(long2)")

    with utils.raises(IterableTooLong):
        e("long.update({'foo': 'bar'})")

    with utils.raises(IterableTooLong):
        e("long['foo'] = 'bar'")

    if PY_39:
        with utils.raises(IterableTooLong):
            e("long | {'foo': 'bar'}")

        with utils.raises(IterableTooLong):
            e("long_copy |= long2")

    with utils.raises(IterableTooLong):
        e("toolong = {f'{i:03}': 'a' for i in range(201)}")

    with utils.raises(IterableTooLong):
        e("toolong2 = dict((f'{i:03}', 'a') for i in range(200, 343))")

    with utils.raises(IterableTooLong):
        e("{**long, **long2}")

    # we should be able to unpack at the limit
    e("{**long}")


def test_that_it_still_works_right(i, e):
    e("l = [1, 2]")
    e("d = {1: 1}")
    e("s = {1, 2}")

    e("l.append(3)")
    assert e("l") == [1, 2, 3]
    assert isinstance(i.names["l"], i._list)

    e("s.add(3)")
    assert e("s") == {1, 2, 3}
    assert isinstance(i.names["s"], i._set)

    e("d.update({2: 2})")
    assert e("d") == {1: 1, 2: 2}
    assert isinstance(i.names["d"], i._dict)

    pop = e("d.pop(2)")
    assert e("d") == {1: 1}
    assert pop == 2
    assert isinstance(i.names["d"], i._dict)

    e("d.update({2: 2})")

    pop = e("d.pop(2, 3)")
    assert e("d") == {1: 1}
    assert pop == 2
    assert isinstance(i.names["d"], i._dict)

    pop = e("d.pop(2, 3)")
    assert e("d") == {1: 1}
    assert pop == 3
    assert isinstance(i.names["d"], i._dict)

    with utils.raises(KeyError):
        e("d.pop(2)")


def test_types(i, e):
    # when we have a compound type as a builtin, users shouldn't be able to modify it directly...
    i.builtins.update({"rl": [1, 2], "rd": {1: 1, 2: 2}})

    e("rl[1] = 3")
    e("rd[2] = 3")

    assert i.names["rl"] == [1, 2]
    assert i.names["rd"] == {1: 1, 2: 2}

    # but setting it to a name is fine
    e("l = rl")
    e("d = rd")

    e("l[1] = 3")
    e("d[2] = 3")

    assert i.names["l"] == [1, 3]
    assert i.names["d"] == {1: 1, 2: 3}


def test_types_again(i, e):
    e("a = [1, 2, 3]")
    e("b = list('123')")
    assert type(i.names["a"]) is type(i.names["b"]) is i._list

    e("a = {1, 2, 3}")
    e("b = set('123')")
    assert type(i.names["a"]) is type(i.names["b"]) is i._set

    e("a = {1: 1, 2: 2}")
    e("b = dict(((1, 1), (2, 2)))")
    assert type(i.names["a"]) is type(i.names["b"]) is i._dict

    e("a = 'foobar'")
    e("b = str(123)")
    assert type(i.names["a"]) is type(i.names["b"]) is i._str

    i.builtins["typeof"] = lambda o: type(o).__name__
    assert e("typeof(a)") == "str"


def test_int_limits(e):
    max_int = (2**31) - 1
    min_int = -(2**31)
    e(f"max_int = {max_int}")
    e(f"min_int = {min_int}")

    # result is too large
    with utils.raises(NumberTooHigh):
        e("max_int + 1")

    with utils.raises(NumberTooHigh):
        e("max_int - -1")

    with utils.raises(NumberTooHigh):
        e("max_int * 2")

    with utils.raises(NumberTooHigh):
        e("max_int << 1")

    with utils.raises(NumberTooHigh):
        e("max_int * max_int")

    with utils.raises(NumberTooHigh):
        e("2 ** 31")

    with utils.raises(NumberTooHigh):
        e("2 << 31")

    with utils.raises(NumberTooHigh):
        e("min_int - 1")

    with utils.raises(NumberTooHigh):
        e("min_int + -1")

    with utils.raises(NumberTooHigh):
        e("min_int * 2")

    with utils.raises(NumberTooHigh):
        e("min_int << 1")

    with utils.raises(NumberTooHigh):
        e("min_int * -min_int")


def test_int_limits_one_op(e):
    max_int = (2**31) - 1
    min_int = -(2**31)
    e(f"max_int = {max_int}")
    e(f"min_int = {min_int}")

    # one operand is too large
    e(f"over_max_int = {max_int + 1}")
    e(f"under_min_int = {min_int - 1}")

    with utils.raises(NumberTooHigh):
        e("over_max_int - 1")

    with utils.raises(NumberTooHigh):
        e("1 - over_max_int")

    with utils.raises(NumberTooHigh):
        e("over_max_int + -1")

    with utils.raises(NumberTooHigh):
        e("-1 + over_max_int")

    with utils.raises(NumberTooHigh):
        e("over_max_int * 1")

    with utils.raises(NumberTooHigh):
        e("1 * over_max_int")

    with utils.raises(NumberTooHigh):
        e("under_min_int - 1")

    with utils.raises(NumberTooHigh):
        e("1 - under_min_int")

    with utils.raises(NumberTooHigh):
        e("under_min_int + -1")

    with utils.raises(NumberTooHigh):
        e("-1 + under_min_int")

    with utils.raises(NumberTooHigh):
        e("under_min_int * 1")

    with utils.raises(NumberTooHigh):
        e("1 * under_min_int")


def test_int_limits_not_floats(e):
    max_int = (2**31) - 1
    min_int = -(2**31)
    e(f"max_int = {max_int}")
    e(f"min_int = {min_int}")

    # floats are fine
    assert e("max_int * 1.5") == max_int * 1.5
    assert e("max_int / 0.5") == max_int / 0.5
    assert e("max_int // 0.5") == max_int // 0.5
    assert type(e("max_int // 0.5")) is float

    assert e("min_int * 1.5") == min_int * 1.5
    assert e("min_int / 0.5") == min_int / 0.5
    assert e("min_int // 0.5") == min_int // 0.5
    assert type(e("min_int // 0.5")) is float


@pytest.mark.timeout(3)  # list mult should be fast, even if we do it a lot
def test_list_mult_speed(i):
    expr = """
    while True:
        a = [0] * 10000
    """.strip()
    with temp_limits(i, max_loops=10000, max_const_len=10000):
        with utils.raises(TooManyStatements):
            i.execute(expr)


def test_loop_limit(i):
    expr = """
    while True:
        pass
    """.strip()

    expr2 = """
    for _ in [0] * 101:
        pass
    """.strip()
    with temp_limits(i, max_loops=100):
        with utils.raises(TooManyStatements):
            i.execute(expr)

        with utils.raises(TooManyStatements):
            i.execute(expr2)


def test_starred_limit(i, e):
    i._names["long"] = range(101)
    i._names["dict_long"] = {i: x for i, x in enumerate(range(100, -1, -1))}
    with temp_limits(i, max_loops=100):
        with utils.raises(IterableTooLong):
            i.execute("[*long]")

        with utils.raises(IterableTooLong):
            i.execute("{**dict_long}")


def test_stmt_limit(i):
    expr = """
    a = 1 + 1 + 1 + 1 + 1 + 1 + 1 + 1 + 1 + 1 + 1 + 1 + 1 + 1 + 1 + 1 + 1 + 1 + 1 + 1 + 1 + 1 + 1 + 1
    """.strip()
    with temp_limits(i, max_statements=10):
        with utils.raises(TooManyStatements):
            i.execute(expr)


def test_func_limit(i, e):
    # functions should not be able to escape
    e("""long = "f"*999""")
    e("""
def test(*args):
    return args
""")

    e("test(long)")
    with utils.raises(IterableTooLong):
        e("test(long, long)")

    # should also apply to lambda functions
    e("""test2 = lambda *args: args""")
    e("test(long)")
    with utils.raises(IterableTooLong):
        e("test(long, long)")

    i.builtins["max"] = max

    # should not apply to builtins
    e("max(long, long)")


def test_int_to_bytes_limit(i, e):
    assert e("(255).to_bytes(2, 'big')") == b"\x00\xff"
    assert len(e("(1).to_bytes(1000, 'big')")) == 1000
    for expr in (
        "(1).to_bytes(1001, 'big')",
        "(1).to_bytes(length=1001, byteorder='big')",
        "int.to_bytes(1, 1001, 'big')",
        "True.to_bytes(1001, 'little')",
    ):
        with utils.raises(IterableTooLong):
            e(expr)


def test_int_to_bytes_limit_simple_interpreter():
    from draconic import SimpleInterpreter

    interpreter = SimpleInterpreter(config=DraconicConfig(max_const_len=1000))
    with utils.raises(IterableTooLong):
        interpreter.eval("(1).to_bytes(1001, 'big')")


def test_bytes_growth_limits(i, e):
    i.builtins["b"] = b"\x00" * 10
    i.builtins["tab"] = b"\t" * 10
    i.builtins["bytes"] = bytes
    assert len(e("b.center(20)")) == 20
    assert e("b.replace(b[:1], b[:2])") == b"\x00" * 20
    assert e("b[:1].join([b, b])") == b"\x00" * 21
    for expr in (
        "b.center(1001)",
        "b.ljust(1001)",
        "b.rjust(1001)",
        "b.zfill(1001)",
        "tab.expandtabs(101)",
        "b.replace(b[:1], b * 11)",
        "b.join([b] * 100)",
        "bytes.center(b, 1001)",
    ):
        with utils.raises(IterableTooLong):
            e(expr)


def test_shared_references_count_toward_limits(i, ex):
    # the same list referenced many times inside one literal counts at every reference
    refs = ", ".join(["a"] * 20)
    with utils.raises(IterableTooLong):
        ex(f"a = [0] * 100\nb = [{refs}]")


def test_nested_shared_references_str():
    # the list fits max_const_len (each level is 10 references to the one below), but its string would not
    config = DraconicConfig(max_output_len=10_000)
    interpreter = DraconicInterpreter(config=config, builtins={"range": range, "str": str, "len": len})
    expr = """
a = ["x" * 100]
for _ in range(3):
    b = []
    for _ in range(10):
        b.append(a)
    a = b
return {}
"""
    for conversion in ("str(a)", "f'{a}'", "'%s' % (a,)", "str({'k': a})", "str({'k': [a]})"):
        with utils.raises(IterableTooLong):
            interpreter.execute(expr.format(conversion))
    assert interpreter.execute(expr.format("len(str(a[0][0]))")) == len(str([["x" * 100]] * 10))
    # growing a shared child after it was placed in a parent is caught when the parent is converted
    with utils.raises(IterableTooLong):
        interpreter.execute(
            "a = ['x']\nb = []\nfor _ in range(100):\n    b.append(a)\na.extend(['y' * 100] * 10)\nreturn str(b)"
        )


def test_cyclic_structures_still_convert(i, ex):
    assert ex("a = [1]\na.append(a)\nreturn str(a)") == "[1, [...]]"
    assert ex("d = {}\nd['self'] = d\nreturn str(d)") == "{'self': {...}}"


def test_max_output_len_config():
    interpreter = DraconicInterpreter(config=DraconicConfig(max_output_len=100))
    interpreter.builtins.update(str=str, range=range)
    assert interpreter.execute("return str(list(range(10)))") == str(list(range(10)))
    for expr in ("str(list(range(100)))", "str(set(range(100)))", "str({x: x for x in range(100)})"):
        with utils.raises(IterableTooLong):
            interpreter.execute(f"return {expr}")


def test_total_output_len_covers_unchecked_wrappers():
    config = DraconicConfig(max_output_len=100, max_total_output_len=300)
    interpreter = DraconicInterpreter(config=config, builtins={"str": str, "range": range})
    setup = "a = list(range(25))\nd = {1: a, 2: a, 3: a, 4: a, 5: a, 6: a}\ndef f(*x):\n    return x\n"
    for expr in ("str((a, a, a, a, a, a))", "str(tuple([a] * 6))", "str(d.values())", "str(f(a, a, a, a, a, a))"):
        with utils.raises(IterableTooLong):
            interpreter.execute(f"{setup}return {expr}")


def test_total_output_len_resets_per_execution():
    config = DraconicConfig(max_total_output_len=1000)
    interpreter = DraconicInterpreter(config=config, builtins={"str": str, "range": range})
    for _ in range(5):  # each run converts ~400 chars; only the sum within one run counts
        assert interpreter.execute("return str(list(range(100)))") == str(list(range(100)))
    with utils.raises(IterableTooLong):
        interpreter.execute("a = list(range(100))\nfor _ in range(5):\n    str(a)")


def test_list_additions_count_item_size(i, ex):
    i.builtins.update(range=range, str=str, tuple=tuple)
    for add in ("l.append(s)", "l.insert(0, s)", "l[0:0] = [s]"):
        # one 900-char item fits, but it must count as 900, not 1, so the multiplication is refused
        with utils.raises(IterableTooLong):
            ex(f"s = 'x' * 900\nl = []\n{add}\nl2 = l * 100")
    with utils.raises(IterableTooLong):
        ex("s = 'x' * 900\nl = []\nl.append(s)\nl.append(s)")


def test_list_removals_release_item_size(i, ex):
    i.builtins.update(range=range)
    # 50 rounds of adding and removing a 900-char item never hold more than one at a time
    for remove in ("l.pop()", "l.remove(s)", "l[0] = 0", "l[0:1] = []"):
        assert (
            ex(
                f"s = 'x' * 900\nl = [0]\nfor _ in range(50):\n    l[0:1] = [s]\n    {remove}\n    l[0:0] = [0]\nreturn 1"
            )
            == 1
        )


def test_dict_keys_count_toward_limits(i, ex):
    i.builtins.update(range=range, str=str, len=len)
    with utils.raises(IterableTooLong):
        ex("d = {}\nfor n in range(20):\n    d['x' * 90 + str(n)] = 0")
    with utils.raises(IterableTooLong):
        ex("d = {}\nfor n in range(20):\n    d.setdefault('x' * 90 + str(n), 0)")
    # overwriting or deleting keys releases their size
    assert ex("d = {}\nfor n in range(200):\n    d['k' * 90] = n\nreturn d['k' * 90]") == 199
    assert (
        ex("d = {}\nfor n in range(200):\n    d['k' * 90 + str(n)] = n\n    d.pop('k' * 90 + str(n))\nreturn len(d)")
        == 0
    )


def _interpreter(**limits):
    # no "str" builtin: the interpreter's own str is the size-checked one
    return DraconicInterpreter(config=DraconicConfig(**limits), builtins={"range": range, "len": len})


def test_conversions_of_unchecked_containers():
    interpreter = _interpreter(max_output_len=1000)
    setup = "t = tuple(range(300))\nd = {n: n for n in range(300)}\n"
    for expr in ("str(t)", "f'{t}'", "'%s' % (t,)", "str(d.keys())", "f'{d.items()}'"):
        with utils.raises(IterableTooLong):
            interpreter.execute(f"{setup}return {expr}")
    assert interpreter.execute("return str((1, 2)) + f'{(3,)}' + '%s' % ((4,),)") == "(1, 2)(3,)(4,)"


def test_finally_cannot_swallow_limit_errors():
    interpreter = _interpreter(max_const_len=1000)
    for exit_ in ("continue", "break"):
        with utils.raises(IterableTooLong):
            interpreter.execute(f"for _ in range(3):\n    try:\n        x = [0] * 2000\n    finally:\n        {exit_}")
    with utils.raises(IterableTooLong):
        interpreter.execute("def f():\n    try:\n        x = [0] * 2000\n    finally:\n        return 1\nreturn f()")
    # ordinary exceptions are still replaced by a return in finally, as in Python
    assert interpreter.execute("def f():\n    try:\n        x = 1 / 0\n    finally:\n        return 1\nreturn f()") == 1


def test_rejected_conversion_does_not_use_total_output_len():
    config = DraconicConfig(max_output_len=100, max_total_output_len=300)
    interpreter = DraconicInterpreter(config=config, builtins={"str": str, "range": range})
    with utils.raises(IterableTooLong):
        interpreter.execute("a = list(range(100))\nstr(a)")
    interpreter._preflight = lambda: None  # keep the counter, as Avrae's ScriptingEvaluator does
    assert interpreter.execute("return str([1, 2])") == "[1, 2]"


def test_negative_list_multiplier_cannot_hide_size():
    with utils.raises(IterableTooLong):
        _interpreter(max_const_len=1000).execute(
            "x = [0] * -(2 ** 60)\nx.append(0)\nfor _ in range(12):\n    x.extend(x)"
        )


def test_set_add_counts_element_size():
    with utils.raises(IterableTooLong):
        _interpreter(max_const_len=1000).execute("s = set()\nfor n in range(100):\n    s.add('x' * 90 + str(n))")


def test_repr_len_counts_escapes():
    interpreter = _interpreter(max_output_len=1000)
    for value in ("'\\U000e0001' * 200", "'\\x00' * 300"):
        with utils.raises(IterableTooLong):
            interpreter.execute(f"return str([{value}])")


def test_repeated_updates_do_not_accumulate_size():
    interpreter = _interpreter(max_const_len=1000)
    for loop in (
        "d = {}\nfor n in range(3000):\n    d['k'] = n\n    d.clear()",
        "d = {}\nfor n in range(3000):\n    d.update({'k': 'x' * 10})",
        "d = {}\nfor n in range(3000):\n    d['k' + str(n % 5)] = 'v'\n    d.popitem()",
        "s = set()\nfor n in range(3000):\n    s.add('x' * 10)\n    s.discard('x' * 10)",
        "s = {'x' * 10}\nfor n in range(3000):\n    s.add('x' * 10)",
        "s = set()\nfor n in range(3000):\n    s.update({'a', 'b'})\n    s.difference_update({'a'})",
    ):
        interpreter.execute(loop)
