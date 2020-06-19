"""
Test cases adapted from SimpleEval: https://github.com/danthedeckie/simpleeval
"""
import ast
import operator
import sys
import unittest

from draconic import AnnotatedException, DraconicException, DraconicInterpreter, DraconicSyntaxError, \
    FeatureNotAvailable, InvalidExpression, IterableTooLong, NotDefined, NumberTooHigh


class DRYTest(unittest.TestCase):
    """ Stuff we need to do every test, let's do here instead..
        Don't Repeat Yourself. """

    def setUp(self):
        """ initialize a SimpleEval """
        self.s = DraconicInterpreter()

    def assertRaises(self, expected_exception, *args, **kwargs):
        if not issubclass(expected_exception, DraconicException):
            return super().assertRaises((AnnotatedException, expected_exception))
        return super().assertRaises(expected_exception)

    def t(self, expr, shouldbe):  # pylint: disable=invalid-name
        """ test an evaluation of an expression against an expected answer """
        return self.assertEqual(self.s.eval(expr), shouldbe)


class TestBasic(DRYTest):
    """ Simple expressions. """

    def test_maths_with_ints(self):
        """ simple maths expressions """

        self.t("21 + 21", 42)
        self.t("6*7", 42)
        self.t("20 + 1 + (10*2) + 1", 42)
        self.t("100/10", 10)
        self.t("12*12", 144)
        self.t("2 ** 10", 1024)
        self.t("100 % 9", 1)

    def test_bools_and_or(self):
        self.t('True and ""', "")
        self.t('True and False', False)
        self.t('True or False', True)
        self.t('False or False', False)
        self.t('1 - 1 or 21', 21)
        self.t('1 - 1 and 11', 0)
        self.t('110 == 100 + 10 and True', True)
        self.t('110 != 100 + 10 and True', False)
        self.t('False or 42', 42)

        self.t('False or None', None)
        self.t('None or None', None)

        self.s.names = {'out': True, 'position': 3}
        self.t('(out and position <=6 and -10)'
               ' or (out and position > 6 and -5)'
               ' or (not out and 15)', -10)

    def test_not(self):
        self.t('not False', True)
        self.t('not True', False)
        self.t('not 0', True)
        self.t('not 1', False)

    def test_maths_with_floats(self):
        self.t("11.02 - 9.1", 1.92)
        self.t("29.1+39", 68.1)

    def test_comparisons(self):
        # GT & LT:
        self.t("1 > 0", True)
        self.t("100000 < 28", False)
        self.t("-2 < 11", True)
        self.t("+2 < 5", True)
        self.t("0 == 0", True)

        # GtE, LtE
        self.t("-2 <= -2", True)
        self.t("2 >= 2", True)
        self.t("1 >= 12", False)
        self.t("1.09 <= 1967392", True)

        self.t('1 < 2 < 3 < 4', 1 < 2 < 3 < 4)
        self.t('1 < 2 > 3 < 4', 1 < 2 > 3 < 4)

        self.t('1<2<1+1', 1 < 2 < 1 + 1)
        self.t('1 == 1 == 2', 1 == 1 == 2)
        self.t('1 == 1 < 2', 1 == 1 < 2)

    def test_mixed_comparisons(self):
        self.t("1 > 0.999999", True)
        self.t("1 == True", True)  # Note ==, not 'is'.
        self.t("0 == False", True)  # Note ==, not 'is'.
        self.t("False == False", True)
        self.t("False < True", True)

    def test_if_else(self):
        """ x if y else z """

        # and test if/else expressions:
        self.t("'a' if 1 == 1 else 'b'", 'a')
        self.t("'a' if 1 > 2 else 'b'", 'b')

        # and more complex expressions:
        self.t("'a' if 4 < 1 else 'b' if 1 == 2 else 'c'", 'c')

    def test_default_conversions(self):
        """ conversion between types """

        self.t('int("20") + int(0.22*100)', 42)
        self.t('float("42")', 42.0)
        self.t('"Test Stuff!" + str(11)', "Test Stuff!11")

    def test_slicing(self):
        self.s.operators[ast.Slice] = (operator.getslice
                                       if hasattr(operator, "getslice") else operator.getitem)
        self.t("'hello'[1]", "e")
        self.t("'hello'[:]", "hello")
        self.t("'hello'[:3]", "hel")
        self.t("'hello'[3:]", "lo")
        self.t("'hello'[::2]", "hlo")
        self.t("'hello'[::-1]", "olleh")
        self.t("'hello'[3::]", "lo")
        self.t("'hello'[:3:]", "hel")
        self.t("'hello'[1:3]", "el")
        self.t("'hello'[1:3:]", "el")
        self.t("'hello'[1::2]", "el")
        self.t("'hello'[:1:2]", "h")
        self.t("'hello'[1:3:1]", "el")
        self.t("'hello'[1:3:2]", "e")

        with self.assertRaises(IndexError):
            self.t("'hello'[90]", 0)

        self.t('"spam" not in "my breakfast"', True)
        self.t('"silly" in "ministry of silly walks"', True)
        self.t('"I" not in "team"', True)
        self.t('"U" in "RUBBISH"', True)

    def test_is(self):
        self.t('1 is 1', True)
        self.t('1 is 2', False)
        self.t('1 is "a"', False)
        self.t('1 is None', False)
        self.t('None is None', True)

        self.t('1 is not 1', False)
        self.t('1 is not 2', True)
        self.t('1 is not "a"', True)
        self.t('1 is not None', True)
        self.t('None is not None', False)

    def test_fstring(self):
        if sys.version_info >= (3, 6, 0):
            self.t('f""', "")
            self.t('f"stuff"', "stuff")
            self.t('f"one is {1} and two is {2}"', "one is 1 and two is 2")
            self.t('f"1+1 is {1+1}"', "1+1 is 2")
            self.t('f"{\'dramatic\':!<11}"', "dramatic!!!")


class TestFunctions(DRYTest):
    """ Functions for expressions to play with """

    def test_methods(self):
        self.t('"WORD".lower()', 'word')

    def test_function_args_none(self):
        def foo():
            return 42

        self.s.names = {**self.s.names, 'foo': foo}
        self.t('foo()', 42)

    def test_function_args_required(self):
        def foo(toret):
            return toret

        self.s.names = {**self.s.names, 'foo': foo}
        with self.assertRaises(TypeError):
            self.t('foo()', 42)

        self.t('foo(12)', 12)
        self.t('foo(toret=100)', 100)

    def test_function_args_defaults(self):
        def foo(toret=9999):
            return toret

        self.s.names = {**self.s.names, 'foo': foo}
        self.t('foo()', 9999)

        self.t('foo(12)', 12)
        self.t('foo(toret=100)', 100)

    def test_function_args_bothtypes(self):
        def foo(mult, toret=100):
            return toret * mult

        self.s.names = {**self.s.names, 'foo': foo}
        with self.assertRaises(TypeError):
            self.t('foo()', 9999)

        self.t('foo(2)', 200)

        with self.assertRaises(TypeError):
            self.t('foo(toret=100)', 100)

        self.t('foo(4, toret=4)', 16)
        self.t('foo(mult=2, toret=4)', 8)
        self.t('foo(2, 10)', 20)


class TestNewFeatures(DRYTest):
    """ Tests which will break when new features are added..."""

    def test_lambda(self):
        with self.assertRaises(FeatureNotAvailable):
            self.t('lambda x:22', None)

    def test_lambda_application(self):
        with self.assertRaises(FeatureNotAvailable):
            self.t('(lambda x:22)(44)', None)


class TestTryingToBreakOut(DRYTest):
    """ Test various weird methods to break the security sandbox... """

    def setUp(self):
        super().setUp()
        self.s._config.max_const_len = 100000

    def test_import(self):
        """ usual suspect. import """
        # cannot import things:
        with self.assertRaises(FeatureNotAvailable):
            self.t("import sys", None)

    def test_long_running(self):
        """ exponent operations can take a long time. """
        old_max = self.s._config.max_power_base

        self.t("9**9**3", 9 ** 9 ** 3)

        with self.assertRaises(NumberTooHigh):
            self.t("9**9**8", 0)

        # and does limiting work?

        self.s._config.max_power_base = 100

        with self.assertRaises(NumberTooHigh):
            self.t("101**2", 0)

        # good, so set it back:

        self.s._config.max_power_base = old_max

    def test_encode_bignums(self):
        # thanks gk
        if hasattr(1, 'from_bytes'):  # python3 only
            with self.assertRaises(IterableTooLong):
                self.t('(1).from_bytes(("123123123123123123123123").encode()*999999, "big")', 0)

    def test_string_length(self):
        with self.assertRaises(IterableTooLong):
            self.t("50000*'text'", 0)

        with self.assertRaises(IterableTooLong):
            self.t("'text'*50000", 0)

        with self.assertRaises(IterableTooLong):
            self.t("('text'*50000)*1000", 0)

        with self.assertRaises(IterableTooLong):
            self.t("(50000*'text')*1000", 0)

        self.t("'stuff'*20000", 20000 * 'stuff')

        self.t("20000*'stuff'", 20000 * 'stuff')

        with self.assertRaises(IterableTooLong):
            self.t("('stuff'*20000) + ('stuff'*20000) ", 0)

        with self.assertRaises(IterableTooLong):
            self.t("'stuff'*100000", 100000 * 'stuff')

        with self.assertRaises(IterableTooLong):
            self.t("'" + (10000 * "stuff") + "'*100", 0)

        with self.assertRaises(IterableTooLong):
            self.t("'" + (50000 * "stuff") + "'", 0)

        if sys.version_info >= (3, 6, 0):
            with self.assertRaises(IterableTooLong):
                self.t("f'{\"foo\"*50000}'", 0)

    def test_bytes_array_test(self):
        self.t("'20000000000000000000'.encode() * 5000",
               '20000000000000000000'.encode() * 5000)

        with self.assertRaises(IterableTooLong):
            self.t("'123121323123131231223'.encode() * 5000", 20)

    def test_list_length_test(self):
        self.t("'spam spam spam'.split() * 5000", ['spam', 'spam', 'spam'] * 5000)

        with self.assertRaises(IterableTooLong):
            self.t("('spam spam spam' * 5000).split() * 5000", None)

    def test_function_globals_breakout(self):
        """ by accessing function.__globals__ or func_... """
        # thanks perkinslr.

        self.s.names = {**self.s.names, 'x': lambda y: y + y}
        self.t('x(100)', 200)

        with self.assertRaises(FeatureNotAvailable):
            self.t('x.__globals__', None)

        class EscapeArtist(object):
            @staticmethod
            def trapdoor():
                return 42

            @staticmethod
            def _quasi_private():
                return 84

        self.s.names = {**self.s.names, 'houdini': EscapeArtist()}

        with self.assertRaises(FeatureNotAvailable):
            self.t('houdini.trapdoor.__globals__', 0)

        with self.assertRaises(FeatureNotAvailable):
            self.t('houdini.trapdoor.func_globals', 0)

        with self.assertRaises(FeatureNotAvailable):
            self.t('houdini._quasi_private()', 0)

        # and test for changing '_' to '__':

        dis = self.s._config.disallow_prefixes
        self.s._config.disallow_prefixes = ['func_']

        self.t('houdini.trapdoor()', 42)
        self.t('houdini._quasi_private()', 84)

        # and return things to normal

        self.s._config.disallow_prefixes = dis

    def test_mro_breakout(self):
        class Blah(object):
            x = 42

        self.s.names = {**self.s.names, 'b': Blah}

        with self.assertRaises(FeatureNotAvailable):
            self.t('b.mro()', None)

    def test_builtins_private_access(self):
        # explicit attempt of the exploit from perkinslr
        with self.assertRaises(FeatureNotAvailable):
            self.t("True.__class__.__class__.__base__.__subclasses__()[-1]"
                   ".__init__.func_globals['sys'].exit(1)", 42)

    def test_string_format(self):
        # python has so many ways to break out!
        with self.assertRaises(FeatureNotAvailable):
            self.t('"{string.__class__}".format(string="things")', 0)

        with self.assertRaises(FeatureNotAvailable):
            self.s.names = {**self.s.names, 'x': {"a": 1}}
            self.t('"{a.__class__}".format_map(x)', 0)

        if sys.version_info >= (3, 6, 0):
            self.s.names = {**self.s.names, 'x': 42}

            with self.assertRaises(FeatureNotAvailable):
                self.t('f"{x.__class__}"', 0)

            self.s.names = {**self.s.names, 'x': lambda y: y}

            with self.assertRaises(FeatureNotAvailable):
                self.t('f"{x.__globals__}"', 0)

            class EscapeArtist(object):
                @staticmethod
                def trapdoor():
                    return 42

                @staticmethod
                def _quasi_private():
                    return 84

            self.s.names = {**self.s.names, 'houdini': EscapeArtist()}  # let's just retest this, but in a f-string

            with self.assertRaises(FeatureNotAvailable):
                self.t('f"{houdini.trapdoor.__globals__}"', 0)

            with self.assertRaises(FeatureNotAvailable):
                self.t('f"{houdini.trapdoor.func_globals}"', 0)

            with self.assertRaises(FeatureNotAvailable):
                self.t('f"{houdini._quasi_private()}"', 0)

            # and test for changing '_' to '__':

            dis = self.s._config.disallow_prefixes
            self.s._config.disallow_prefixes = ['func_']

            self.t('f"{houdini.trapdoor()}"', "42")
            self.t('f"{houdini._quasi_private()}"', "84")

            # and return things to normal

            self.s._config.disallow_prefixes = dis


class TestCompoundTypes(DRYTest):
    """ Test the compound-types edition of the library """

    def test_dict(self):
        self.t('{}', {})
        self.t('{"foo": "bar"}', {'foo': 'bar'})
        self.t('{"foo": "bar"}["foo"]', 'bar')
        self.t('dict()', {})
        self.t('dict(a=1)', {'a': 1})

    def test_dict_contains(self):
        self.t('{"a":22}["a"]', 22)
        with self.assertRaises(KeyError):
            self.t('{"a":22}["b"]', 22)

        self.t('{"a": 24}.get("b", 11)', 11)
        self.t('"a" in {"a": 24}', True)

    def test_tuple(self):
        self.t('()', ())
        self.t('(1,)', (1,))
        self.t('(1, 2, 3, 4, 5, 6)', (1, 2, 3, 4, 5, 6))
        self.t('(1, 2) + (3, 4)', (1, 2, 3, 4))
        self.t('(1, 2, 3)[1]', 2)
        self.t('tuple()', ())
        self.t('tuple("foo")', ('f', 'o', 'o'))

    def test_tuple_contains(self):
        self.t('("a","b")[1]', 'b')
        with self.assertRaises(IndexError):
            self.t('("a","b")[5]', 'b')
        self.t('"a" in ("b","c","a")', True)

    def test_list(self):
        self.t('[]', [])
        self.t('[1]', [1])
        self.t('[1, 2, 3, 4, 5]', [1, 2, 3, 4, 5])
        self.t('[1, 2, 3][1]', 2)
        self.t('list()', [])
        self.t('list("foo")', ['f', 'o', 'o'])

    def test_list_contains(self):
        self.t('["a","b"][1]', 'b')
        with self.assertRaises(IndexError):
            self.t('("a","b")[5]', 'b')

        self.t('"b" in ["a","b"]', True)

    def test_set(self):
        self.t('{1}', {1})
        self.t('{1, 2, 1, 2, 1, 2, 1}', {1, 2})
        self.t('set()', set())
        self.t('set("foo")', {'f', 'o'})

        self.t('2 in {1,2,3,4}', True)
        self.t('22 not in {1,2,3,4}', True)

    def test_not(self):
        self.t('not []', True)
        self.t('not [0]', False)
        self.t('not {}', True)
        self.t('not {0: 1}', False)
        self.t('not {0}', False)

    def test_use_func(self):
        self.s = DraconicInterpreter(builtins={"list": list, "map": map, "str": str})
        self.t('list(map(str, [-1, 0, 1]))', ['-1', '0', '1'])
        with self.assertRaises(NotDefined):
            self.s.eval('list(map(bad, [-1, 0, 1]))')

        with self.assertRaises(NotDefined):
            self.s.eval('dir(str)')
        with self.assertRaises(FeatureNotAvailable):
            self.s.eval('str.__dict__')

        self.s = DraconicInterpreter(builtins={"dir": dir, "str": str})
        self.t('dir(str)', dir(str))


class TestComprehensions(DRYTest):
    """ Test the comprehensions support of the compound-types edition of the class. """

    def test_basic(self):
        self.t('[a + 1 for a in [1,2,3]]', [2, 3, 4])
        self.t('{a + 1 for a in [1,2,3]}', {2, 3, 4})
        self.t('{a + 1: a - 1 for a in [1,2,3]}', {2: 0, 3: 1, 4: 2})

    def test_setcomp(self):
        self.t('{0 for a in [1,2,3]}', {0})
        self.t('{a % 10 for a in [5,10,15,20]}', {0, 5})

    def test_genexp(self):
        self.t('list(a + 1 for a in [1,2,3])', [2, 3, 4])

    def test_with_self_reference(self):
        self.t('[a + a for a in [1,2,3]]', [2, 4, 6])
        self.t('{a + a for a in [1,2,3]}', {2, 4, 6})
        self.t('{a: a for a in [1,2,3]}', {1: 1, 2: 2, 3: 3})

    def test_with_if(self):
        self.t('[a for a in [1,2,3,4,5] if a <= 3]', [1, 2, 3])
        self.t('{a for a in [1,2,3,4,5] if a <= 3}', {1, 2, 3})
        self.t('{a: a for a in [1,2,3,4,5] if a <= 3}', {1: 1, 2: 2, 3: 3})

    def test_with_multiple_if(self):
        self.t('[a for a in [1,2,3,4,5] if a <= 3 if a > 1 ]', [2, 3])
        self.t('{a for a in [1,2,3,4,5] if a <= 3 if a > 1 }', {2, 3})
        self.t('{a:a for a in [1,2,3,4,5] if a <= 3 if a > 1 }', {2: 2, 3: 3})

    def test_attr_access_fails(self):
        with self.assertRaises(FeatureNotAvailable):
            self.t('[a.__class__ for a in [1,2,3]]', None)
        with self.assertRaises(FeatureNotAvailable):
            self.t('{a.__class__ for a in [1,2,3]}', None)
        with self.assertRaises(FeatureNotAvailable):
            self.t('{a.__class__: a for a in [1,2,3]}', None)
        with self.assertRaises(FeatureNotAvailable):
            self.t('{a: a.__class__ for a in [1,2,3]}', None)

    def test_unpack(self):
        self.t('[a+b for a,b in ((1,2),(3,4))]', [3, 7])
        self.t('{a+b for a,b in ((1,2),(3,4))}', {3, 7})
        self.t('{a: b for a,b in ((1,2),(3,4))}', {1: 2, 3: 4})

    def test_nested_unpack(self):
        self.t('[a+b+c for a, (b, c) in ((1,(1,1)),(3,(2,2)))]', [3, 7])
        self.t('{a+b+c for a, (b, c) in ((1,(1,1)),(3,(2,2)))}', {3, 7})
        self.t('{a:b+c for a, (b, c) in ((1,(1,1)),(3,(2,2)))}', {1: 2, 3: 4})

    def test_other_places(self):
        self.s.names = {**self.s.names, 'sum': sum}
        self.t('sum([a+1 for a in [1,2,3,4,5]])', 20)
        self.t('sum(a+1 for a in [1,2,3,4,5])', 20)

    def test_external_names_work(self):
        self.s.names = {'x': [22, 102, 12.3]}
        self.t('[a/2 for a in x]', [11.0, 51.0, 6.15])

    def test_multiple_generators(self):
        self.s.names = {**self.s.names, 'range': range}
        s = '[j for i in range(100) if i > 10 for j in range(i) if j < 20]'
        self.t(s, eval(s))

    def test_triple_generators(self):
        self.s.names = {**self.s.names, 'range': range}
        s = '[(a,b,c) for a in range(4) for b in range(a) for c in range(b)]'
        self.t(s, eval(s))

    def test_too_long_generator(self):
        self.s.names = {**self.s.names, 'range': range}
        s = '[j for i in range(1000) if i > 10 for j in range(i) if j < 20]'
        with self.assertRaises(IterableTooLong):
            self.s.eval(s)

    def test_too_long_generator_2(self):
        self.s.names = {**self.s.names, 'range': range}
        s = '[j for i in range(100) if i > 1 for j in range(i+10) if j < 100 for k in range(i*j)]'
        with self.assertRaises(IterableTooLong):
            self.s.eval(s)

    def test_nesting_generators_to_cheat(self):
        self.s.names = {**self.s.names, 'range': range}
        s = '[[[c for c in range(a)] for a in range(b)] for b in range(200)]'

        with self.assertRaises(IterableTooLong):
            self.s.eval(s)

    def test_no_leaking_names(self):
        # see issue #52, failing list comprehensions could leak locals
        with self.assertRaises(NotDefined):
            self.s.eval('[x if x == "2" else y for x in "123"]')

        with self.assertRaises(NotDefined):
            self.s.eval('x')


class TestNames(DRYTest):
    """ 'names', what other languages call variables... """

    def test_none(self):
        """ what to do when names isn't defined, or is 'none' """
        with self.assertRaises(NotDefined):
            self.t("a == 2", None)

        self.s.names["s"] = 21

        with self.assertRaises(NotDefined):
            self.t("s += a", 21)

        self.s.names = {}

        with self.assertRaises(InvalidExpression):
            self.t('s', 21)

        self.s.names = {'a': {'b': {'c': 42}}}

        with self.assertRaises(NotDefined):
            self.t('a.b.d**2', 42)

    def test_dict(self):
        """ using a normal dict for names lookup """

        self.s.names = {'a': 42}
        self.t("a + a", 84)

        self.s.names = {**self.s.names, 'also': 100}

        self.t("a + also - a", 100)

        # and you can assign to those names:
        self.t("a = 200", None)
        self.assertEqual(self.s.names['a'], 200)

        # or assign to lists
        self.t("b = [0]", None)
        self.t("b[0] = 11", None)
        self.assertEqual(self.s.names['b'], [11])

        # and you can get items from a list:
        self.t("b = [6, 7]", None)
        self.t("b[0] * b[1]", 42)

        # or from a dict
        self.t("c = {'i': 11}", None)
        self.t("c['i']", 11)
        self.t("c.get('i')", 11)
        self.t("c.get('j', 11)", 11)
        self.t("c.get('j')", None)

        # you still can assign:
        self.t("c['b'] = 99", None)
        self.assertTrue('b' in self.s.names['c'])

        # and going all 'inception' on it works too:
        self.t("c['c'] = {'c': 11}", None)
        self.t("c['c']['c'] = 21", None)
        self.assertEqual(self.s.names['c']['c']['c'], 21)

    def test_dict_attr_access(self):
        # nested dict
        self.s.names = {'a': {'b': {'c': 42}}}

        self.t("a.b.c*2", 84)

        # no assign to attr
        with self.assertRaises(FeatureNotAvailable):
            self.t("a.b.c = 11", 11)

        # assigning to key works here, but...
        self.t("a['b']['c'] = 11", None)

        # since we passed a real dict in to names, that shouldn't be modifiable by the user
        self.assertEqual(self.s.names['a']['b']['c'], 42)

        with self.assertRaises(FeatureNotAvailable):
            self.t("a.d = 11", 11)

        with self.assertRaises(KeyError):
            self.assertEqual(self.s.names['a']['d'], 11)


class TestWhitespace(DRYTest):
    """ test that incorrect whitespace (preceding/trailing) does matter. """

    def test_no_whitespace(self):
        self.t('200 + 200', 400)

    def test_trailing(self):
        self.t('200 + 200       ', 400)

    def test_preciding_whitespace(self):
        with self.assertRaises(DraconicSyntaxError):
            self.t('    200 + 200', 400)

    def test_preceding_tab_whitespace(self):
        with self.assertRaises(DraconicSyntaxError):
            self.t("\t200 + 200", 400)

    def test_preceding_mixed_whitespace(self):
        with self.assertRaises(DraconicSyntaxError):
            self.t("  \t 200 + 200", 400)

    def test_both_ends_whitespace(self):
        with self.assertRaises(DraconicSyntaxError):
            self.t("  \t 200 + 200  ", 400)


class TestMethodChaining(DRYTest):
    def test_chaining_correct(self):
        """
            Contributed by Khalid Grandi (xaled).
        """

        class A(object):
            def __init__(self):
                self.a = "0"

            def add(self, b):
                self.a += "-add" + str(b)
                return self

            def sub(self, b):
                self.a += "-sub" + str(b)
                return self

            def tostring(self):
                return str(self.a)

        x = A()
        self.s.names = {"x": x}
        self.t("x.add(1).sub(2).sub(3).tostring()", "0-add1-sub2-sub3")


class TestUnusualComparisons(DRYTest):
    def test_custom_comparison_returner(self):
        class Blah(object):
            def __gt__(self, other):
                return self

        b = Blah()
        self.s.names = {'b': b}
        self.t('b > 2', b)


class TestGetItemUnhappy(DRYTest):
    # Again, SqlAlchemy doing unusual things.  Throwing it's own errors, rather than
    # expected types...

    def test_getitem_not_implemented(self):
        class Meh(object):
            def __getitem__(self, key):
                raise NotImplementedError("booya!")

            def __getattr__(self, key):
                return 42

        m = Meh()

        self.assertEqual(m.anything, 42)
        with self.assertRaises(NotImplementedError):
            _ = m['nothing']

        self.s.names = {"m": m}
        self.t("m.anything", 42)

        with self.assertRaises(NotImplementedError):
            self.t("m['nothing']", None)

        self.s.ATTR_INDEX_FALLBACK = False

        self.t("m.anything", 42)

        with self.assertRaises(NotImplementedError):
            self.t("m['nothing']", None)


class TestShortCircuiting(DRYTest):
    def test_shortcircuit_if(self):
        x = []

        def foo(y):
            x.append(y)
            return y

        self.s.names = {**self.s.names, 'foo': foo}
        self.t('foo(1) if foo(2) else foo(3)', 1)
        self.assertListEqual(x, [2, 1])

        x = []
        self.t('42 if True else foo(99)', 42)
        self.assertListEqual(x, [])

    def test_shortcircuit_comparison(self):
        x = []

        def foo(y):
            x.append(y)
            return y

        self.s.names = {**self.s.names, 'foo': foo}
        self.t('foo(11) < 12', True)
        self.assertListEqual(x, [11])
        x = []

        self.t('1 > 2 < foo(22)', False)
        self.assertListEqual(x, [])


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
