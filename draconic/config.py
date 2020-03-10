# default config
DISALLOW_PREFIXES = ['_', 'func_']
DISALLOW_METHODS = ['format', 'format_map', 'mro']
DEFAULT_FUNCTIONS = {"int": int, "float": float, "str": str, "dict": dict, "tuple": tuple, "list": list, "set": set}


class DraconicConfig:
    """A configuration object to pass into the Draconic interpreter."""

    def __init__(self, max_const_len=100000, max_loops=10000, max_statements=100000, max_power_base=1000000,
                 max_power=1000, disallow_prefixes=None, disallow_methods=None,
                 default_names=None, builtins_extend_default=True):
        """
        Configuration object for the Draconic interpreter.

        :param int max_const_len: The maximum length literal that should be allowed to be constructed.
        :param int max_loops: The maximum total number of loops allowed per execution.
        :param int max_statements: The maximum total number of statements allowed per execution.
        :param int max_power_base: The maximum power base (x in x ** y)
        :param int max_power: The maximum power (y in x ** y)
        :param list disallow_prefixes: A list of str - attributes starting with any of these will be inaccessible
        :param list disallow_methods: A list of str - methods named these will not be callable
        :param dict default_names: A dict of str: Any - default names in the runtime
        :param bool builtins_extend_default: If False, ``builtins`` to the interpreter overrides default names
        """
        if disallow_prefixes is None:
            disallow_prefixes = DISALLOW_PREFIXES
        if disallow_methods is None:
            disallow_methods = DISALLOW_METHODS
        if default_names is None:
            default_names = DEFAULT_FUNCTIONS

        self.max_const_len = max_const_len
        self.max_loops = max_loops
        self.max_statements = max_statements
        self.max_power_base = max_power_base
        self.max_power = max_power
        self.disallow_prefixes = disallow_prefixes
        self.disallow_methods = disallow_methods
        self.default_names = default_names
        self.builtins_extend_default = builtins_extend_default
