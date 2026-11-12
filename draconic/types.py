import collections.abc
import operator as op
import threading
from collections import UserList, UserString

from .exceptions import *
from .string import JoinProxy, PRINTF_TEMPLATE_RE, TranslateTableProxy
from .versions import PY_39

__all__ = ("safe_list", "safe_dict", "safe_set", "safe_str", "approx_len_of", "approx_repr_len", "check_output_len")

_sentinel = object()


# ---- size helpers ----
_SCALARS = (int, float, complex, type(None))


# Both helpers memoize each distinct object's size in `sizes` (id -> (obj, size)), so an object referenced
# many times is measured once but counted at every reference: linear in distinct objects + references.
# The tuple keeps obj alive so its id can't be reused mid-walk (e.g. a freed dict.items() tuple).
# A size of None marks an object still being measured, i.e. a reference to it is a cycle.
def approx_len_of(obj, sizes=None):
    """Gets the approximate size of an object, counting every reference to a shared object."""
    if isinstance(obj, (str, bytes, UserString)):
        return len(obj)

    if isinstance(obj, _SCALARS):
        return 0

    if hasattr(obj, "__approx_len__"):
        return obj.__approx_len__

    if sizes is None:
        sizes = {}

    sizes[id(obj)] = (obj, None)
    size = op.length_hint(obj)

    try:
        obj_iter = iter(obj.items() if isinstance(obj, dict) else obj)
    except TypeError:  # object is not iterable
        pass
    else:
        for child in obj_iter:
            if isinstance(child, _SCALARS):
                continue
            seen = sizes.get(id(child))
            size += approx_len_of(child, sizes) if seen is None else seen[1] or 0

    sizes[id(obj)] = (obj, size)
    try:
        setattr(obj, "__approx_len__", size)
    except (AttributeError, TypeError):
        pass

    return size


def approx_repr_len(obj, sizes=None):
    """
    Gets the approximate length of ``repr(obj)`` without building it, counting every reference to a shared object.
    Ignores cached ``__approx_len__`` values, which do not include the size of appended children.
    """
    if isinstance(obj, (str, UserString)):
        return len(obj) + 2
    if isinstance(obj, bytes):
        return len(obj) + 3
    if isinstance(obj, _SCALARS):
        return len(repr(obj))

    if sizes is None:
        sizes = {}
    elif id(obj) in sizes:
        return sizes[id(obj)][1] or 5  # a cycle is printed as [...]

    sizes[id(obj)] = (obj, None)
    if isinstance(obj, dict):
        parts = [approx_repr_len(k, sizes) + approx_repr_len(v, sizes) + 2 for k, v in obj.items()]
    elif isinstance(obj, (list, tuple, set, frozenset, UserList)):
        parts = [approx_repr_len(child, sizes) for child in obj]
    else:
        parts = None

    size = len(repr(obj)) if parts is None else 2 + sum(parts) + 2 * max(len(parts) - 1, 0)
    sizes[id(obj)] = (obj, size)
    return size


def _replace_len(self, old, new, count=-1):
    occurrences = self.count(old) if count < 0 else min(count, self.count(old))
    return len(self) + occurrences * (len(new) - len(old))


# int and bytes methods whose output can be larger than their input, mapped to the output size of a call
_GROWING_METHODS = {
    (int, "to_bytes"): lambda self, length=1, *_, **__: length,
    (bytes, "center"): lambda self, width, *_: width,
    (bytes, "ljust"): lambda self, width, *_: width,
    (bytes, "rjust"): lambda self, width, *_: width,
    (bytes, "zfill"): lambda self, width: width,
    (bytes, "expandtabs"): lambda self, tabsize=8: len(self) + self.count(b"\t") * tabsize,
    (bytes, "replace"): _replace_len,
    (bytes, "join"): lambda self, seq: len(self) * len(seq) + sum(approx_len_of(part) for part in seq),
}


def bound_method(config, obj, attr, method):
    """Wraps int and bytes methods so they raise instead of building output longer than config.max_const_len."""
    cls = obj if isinstance(obj, type) else type(obj)  # int.to_bytes(x, ...) is unbound, (x).to_bytes(...) is bound
    base = next((b for b in (int, bytes) if issubclass(cls, b)), None)
    output_len = _GROWING_METHODS.get((base, attr))
    if output_len is None:
        return method

    def checked(*args, **kwargs):
        if attr == "join" and args:  # consume the iterable so it can be both measured and joined
            args = (*args[:-1], list(args[-1]))
        self_and_args = args if cls is obj else (obj, *args)
        if output_len(*self_and_args, **kwargs) > config.max_const_len:
            _raise_in_context(IterableTooLong, "This value is too large")
        return method(*args, **kwargs)

    return checked


def check_output_len(config, obj):
    """
    Raises if converting obj to a string would exceed config.max_output_len, or push this run's total past
    config.max_total_output_len. The total catches wrappers that are not checked themselves (e.g. a tuple of
    references to one list), whose contents are checked one at a time.
    """
    size = approx_repr_len(obj)
    config.output_len_used += size
    if size > config.max_output_len or config.output_len_used > config.max_total_output_len:
        _raise_in_context(IterableTooLong, "This value is too large to convert to a string")


_repr_guard = threading.local()


def _guarded_repr(config, obj, base_repr):
    """Checks the output length once per top-level conversion; nested conversions are covered by that check."""
    if getattr(_repr_guard, "active", False):
        return base_repr(obj)
    check_output_len(config, obj)
    _repr_guard.active = True
    try:
        return base_repr(obj)
    finally:
        _repr_guard.active = False


# ---- types ----
# each function is a function that returns a class based on Draconic config
# ... look, it works
def safe_list(config):
    class SafeList(UserList):  # extends UserList so that [x] * y returns a SafeList, not a list
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.__approx_len__ = approx_len_of(self)

        def _len_after(self, delta):
            """The size after a change of delta, raising before the change if it would be too long."""
            new_len = approx_len_of(self) + delta
            if new_len > config.max_const_len:
                _raise_in_context(IterableTooLong, "This list is too long")
            return max(new_len, 0)

        # adding an item counts its own size too, like literals, comprehensions, and extend
        def append(self, obj):
            # inlined _len_after with a scalar fast path: append in a loop is the most common list operation
            new_len = self.__approx_len__ + 1 + (0 if isinstance(obj, _SCALARS) else approx_len_of(obj))
            if new_len > config.max_const_len:
                _raise_in_context(IterableTooLong, "This list is too long")
            self.data.append(obj)
            self.__approx_len__ = new_len

        def insert(self, i, obj):
            new_len = self._len_after(approx_len_of(obj) + 1)
            super().insert(i, obj)
            self.__approx_len__ = new_len

        def __setitem__(self, i, item):
            if isinstance(i, slice):
                item = list(item)  # consume the iterable so it can be both measured and assigned
            new_len = self._len_after(approx_len_of(item) - approx_len_of(self.data[i]))
            super().__setitem__(i, item)
            self.__approx_len__ = new_len

        def extend(self, iterable):
            other_len = approx_len_of(iterable)
            if approx_len_of(self) + other_len > config.max_const_len:
                _raise_in_context(IterableTooLong, "This list is too long")
            super().extend(iterable)
            self.__approx_len__ += other_len

        def pop(self, i=-1):
            retval = super().pop(i)
            self.__approx_len__ = self._len_after(-approx_len_of(retval) - 1)
            return retval

        def remove(self, item):
            super().remove(item)
            self.__approx_len__ = self._len_after(-approx_len_of(item) - 1)

        def clear(self):
            super().clear()
            self.__approx_len__ = 0

        def __mul__(self, n):
            # to prevent the recalculation of the length on list mult we manually set a new instance's
            # data and approx len (JIRA-54)
            new = SafeList()
            new.data = self.data * n
            new.__approx_len__ = self.__approx_len__ * n
            return new

        def __add__(self, other):
            new = SafeList()
            new.data = self.data + (other.data if isinstance(other, UserList) else list(other))
            new.__approx_len__ = self.__approx_len__ + approx_len_of(other)
            return new

        def __radd__(self, other):
            new = SafeList()
            new.data = (other.data if isinstance(other, UserList) else list(other)) + self.data
            new.__approx_len__ = approx_len_of(other) + self.__approx_len__
            return new

        def __repr__(self):
            return _guarded_repr(config, self, UserList.__repr__)

    return SafeList


def safe_set(config):
    class SafeSet(set):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.__approx_len__ = approx_len_of(self)

        def union(self, *s):
            if approx_len_of(self) + sum(approx_len_of(other) for other in s) > config.max_const_len:
                _raise_in_context(IterableTooLong, "This set is too large")
            return SafeSet(super().union(*s))

        def __or__(self, other):
            return self.union(other)

        def intersection(self, *s):
            if any(approx_len_of(other) > config.max_const_len for other in s):
                _raise_in_context(IterableTooLong, "This set is too large")
            return SafeSet(super().intersection(*s))

        def __and__(self, other):
            return self.intersection(other)

        def symmetric_difference(self, *s):
            if approx_len_of(self) + sum(approx_len_of(other) for other in s) > config.max_const_len:
                _raise_in_context(IterableTooLong, "This set is too large")
            return SafeSet(super().symmetric_difference(*s))

        def __xor__(self, other):
            return self.symmetric_difference(other)

        # difference not reimplemented as it cannot grow the set and has no cheap approximation for len

        def update(self, *s):
            other_lens = sum(approx_len_of(other) for other in s)
            if approx_len_of(self) + other_lens > config.max_const_len:
                _raise_in_context(IterableTooLong, "This set is too large")
            super().update(*s)
            self.__approx_len__ += other_lens

        def intersection_update(self, *s):
            if any(approx_len_of(other) > config.max_const_len for other in s):
                _raise_in_context(IterableTooLong, "This set is too large")
            super().intersection_update(*s)
            self.__approx_len__ = min(self.__approx_len__, *(approx_len_of(other) for other in s))

        def symmetric_difference_update(self, s):
            total_approx = approx_len_of(self) + approx_len_of(s)
            if total_approx > config.max_const_len:
                _raise_in_context(IterableTooLong, "This set is too large")
            super().symmetric_difference_update(s)
            self.__approx_len__ = total_approx

        # difference_update not reimplemented as it cannot grow the set and has no cheap approximation for len

        def add(self, element):
            if approx_len_of(self) + 1 > config.max_const_len:
                _raise_in_context(IterableTooLong, "This set is too large")
            super().add(element)
            self.__approx_len__ += 1

        def pop(self):
            retval = super().pop()
            self.__approx_len__ -= 1
            return retval

        def remove(self, element):
            super().remove(element)
            self.__approx_len__ -= 1

        # discard not reimplemented as the discarded element may not be a member

        def clear(self):
            super().clear()
            self.__approx_len__ = 0

        def __repr__(self):
            return _guarded_repr(config, self, set.__repr__)

    return SafeSet


def safe_dict(config):
    class SafeDict(dict):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.__approx_len__ = approx_len_of(self)

        def update(self, other_dict=None, **kvs):
            if other_dict is None:
                other_dict = {}

            other_lens = approx_len_of(other_dict) + approx_len_of(kvs)
            if approx_len_of(self) + other_lens > config.max_const_len:
                _raise_in_context(IterableTooLong, "This dict is too large")

            super().update(other_dict, **kvs)
            self.__approx_len__ += other_lens

        def _entry_len(self, key):
            return approx_len_of(key) + approx_len_of(self[key]) + 1

        def __setitem__(self, key, value):
            # a new key counts its own size; overwriting a key swaps the old value's size for the new one
            delta = approx_len_of(value) - (approx_len_of(self[key]) if key in self else -approx_len_of(key) - 1)
            new_len = approx_len_of(self) + delta
            if new_len > config.max_const_len:
                _raise_in_context(IterableTooLong, "This dict is too large")
            super().__setitem__(key, value)
            self.__approx_len__ = max(new_len, 0)

        def setdefault(self, key, default=None):
            if key not in self:
                self[key] = default  # dict.setdefault would skip the size check in __setitem__
            return self[key]

        def pop(self, k, default=_sentinel):
            if k in self:
                self.__approx_len__ = max(self.__approx_len__ - self._entry_len(k), 0)
            return super().pop(k) if default is _sentinel else super().pop(k, default)

        def __delitem__(self, key):
            entry_len = self._entry_len(key)
            super().__delitem__(key)
            self.__approx_len__ = max(self.__approx_len__ - entry_len, 0)

        def __getattr__(self, attr):
            try:
                return self[attr]
            except KeyError:
                raise AttributeError

        if PY_39:

            def __or__(self, other):
                if approx_len_of(self) + approx_len_of(other) > config.max_const_len:
                    _raise_in_context(IterableTooLong, "This dict is too large")

                return SafeDict(super().__or__(other))

        def __repr__(self):
            return _guarded_repr(config, self, dict.__repr__)

    return SafeDict


_real_str = str


def safe_str(config):
    # noinspection PyShadowingBuiltins, PyPep8Naming
    # naming it SafeStr would break typeof backward compatibility :(
    class str(UserString, _real_str):
        def __init__(self, seq):
            if isinstance(seq, UserString):
                self.data = seq.data[:]
            elif isinstance(seq, _real_str):
                self.data = seq
            else:
                self.data = _real_str(seq)

        def center(self, width, *args):
            if width > config.max_const_len:
                _raise_in_context(IterableTooLong, "This str is too large")
            return super().center(width, *args)

        def encode(self, *_, **__):
            _raise_in_context(FeatureNotAvailable, "This method is not allowed")

        def expandtabs(self, tabsize=8):
            if self.count("\t") * tabsize > config.max_const_len:
                _raise_in_context(IterableTooLong, "This str is too large")
            return super().expandtabs(tabsize)

        def format(self, *args, **kwargs):
            _raise_in_context(FeatureNotAvailable, "This method is not allowed")

        def format_map(self, mapping):
            _raise_in_context(FeatureNotAvailable, "This method is not allowed")

        def join(self, seq):
            full_seq = list(seq)  # consume the entire iterator so we can do length checking
            i = JoinProxy(self.__class__, full_seq)  # proxy it so that .join gets the right types
            if len(full_seq) * len(self) + approx_len_of(full_seq) > config.max_const_len:
                _raise_in_context(IterableTooLong, "This str is too large")
            return super().join(i)

        def ljust(self, width, *args):
            if width > config.max_const_len:
                _raise_in_context(IterableTooLong, "This str is too large")
            return super().ljust(width, *args)

        @staticmethod
        def maketrans(*args):
            if len(args) == 1 and isinstance(args[0], dict):
                # str.maketrans expects a dict object and nothing else
                # So SafeDict needs to be cast to dict for the method to work
                return _real_str.maketrans(dict(args[0]))

            if sum(approx_len_of(a) for a in args) > config.max_const_len:
                _raise_in_context(IterableTooLong, "This dict is too large")

            return _real_str.maketrans(*args)

        def replace(self, old, new, maxsplit=-1):
            if maxsplit > 0:
                n = maxsplit
            else:
                n = self.count(old)
            if n * (len(new) - len(old)) + len(self) > config.max_const_len:
                _raise_in_context(IterableTooLong, "This str is too large")
            return super().replace(old, new, maxsplit)

        def rjust(self, width, *args):
            if width > config.max_const_len:
                _raise_in_context(IterableTooLong, "This str is too large")
            return super().rjust(width, *args)

        def translate(self, table):
            # this is kind of a disgusting way to check the worst-case length
            # and is an overestimate by a multiplicative factor of len(table)
            # but it is certainly an overestimate
            if approx_len_of(table) * len(self) > config.max_const_len:
                _raise_in_context(IterableTooLong, "This str is too large")
            table_proxy = TranslateTableProxy(self.__class__, table)
            return super().translate(table_proxy)

        def zfill(self, width):
            if width > config.max_const_len:
                _raise_in_context(IterableTooLong, "This str is too large")
            return super().zfill(width)

        def __format__(self, format_spec):
            # format it using default str formatter
            return self.data.__format__(format_spec)

        def __mod__(self, values):
            new_len_bound = len(self)
            values_is_sequence = isinstance(values, collections.abc.Sequence)
            values_is_mapping = isinstance(values, collections.abc.Mapping)

            # validate that the template is safe (no massive widths/precisions)
            i = 0
            for match in PRINTF_TEMPLATE_RE.finditer(self.data):
                w = match.group("width")
                if w:
                    if w == "*":
                        _raise_in_context(FeatureNotAvailable, "Star precision in printf-style formatting not allowed")
                    else:
                        new_len_bound += int(w)

                p = match.group("precision")
                if p:
                    if p == "*":
                        _raise_in_context(FeatureNotAvailable, "Star precision in printf-style formatting not allowed")
                    else:
                        new_len_bound += int(p)

                mapping_key = match.group("mapping_key")
                if mapping_key is not None:  # '%(foo)s %(foo)s'
                    if not values_is_mapping:  # '%(foo)s' % 0
                        raise TypeError("format requires a mapping")
                    val = values[mapping_key]
                    new_len_bound += approx_len_of(val)
                elif values_is_sequence:  # '%s %s'
                    try:
                        val = values[i]
                    except IndexError:  # '%s %s' % [0]
                        raise TypeError("not enough arguments for format string")
                    new_len_bound += approx_len_of(val)
                elif i > 0:  # '%s %s' % 0
                    raise TypeError("not enough arguments for format string")
                else:  # '%s' % 0
                    new_len_bound += approx_len_of(values)

                if match.group("type") != "%":  # percent literals do not increase index
                    i += 1

                if new_len_bound > config.max_const_len:
                    _raise_in_context(IterableTooLong, "This str is too large")

            return _real_str.__mod__(self.data, values)

    return str
