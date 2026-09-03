from abc import ABC, abstractmethod
from collections import defaultdict
from contextlib import contextmanager
import gdb
import gdb.printing
from .server import client_bool_capability
from .startup import DAPException, in_gdb_thread

all_variables = []


@in_gdb_thread
def clear_vars(event):
    global all_variables
    all_variables = []


gdb.events.cont.connect(clear_vars)


@contextmanager
def _null(**ignore):
    yield


@in_gdb_thread
def apply_format(value_format):
    """Temporarily apply the DAP ValueFormat.
    This returns a new context manager that applies the given DAP
    ValueFormat object globally, then restores gdb's state when finished."""
    if value_format is not None and "hex" in value_format and value_format["hex"]:
        return gdb.with_parameter("output-radix", 16)
    return _null()


class BaseReference(ABC):
    """Represent a variable or a scope.
    This class is just a base class, some methods must be implemented in
    subclasses.
    """

    @in_gdb_thread
    def __init__(self, name):
        """Create a new variable reference with the given name.
        NAME is a string or None.  None means this does not have a
        name, e.g., the result of expression evaluation."""
        all_variables.append(self)
        self._ref = len(all_variables)
        self._name = name
        self.reset_children()

    @in_gdb_thread
    def to_object(self):
        """Return a dictionary that describes this object for DAP.
        The resulting object is a starting point that can be filled in
        further.  See the Scope or Variable types in the spec"""
        result = {"variablesReference": self._ref if self.has_children() else 0}
        if self._name is not None:
            result["name"] = str(self._name)
        return result

    @abstractmethod
    def has_children(self):
        """Return True if this object has children."""
        return False

    def reset_children(self):
        """Reset any cached information about the children of this object."""
        self._children = None
        self._by_name = {}
        self._name_counts = defaultdict(lambda: 1)

    @abstractmethod
    def fetch_one_child(self, index):
        """Fetch one child of this variable.
        INDEX is the index of the child to fetch.
        This should return a tuple of the form (NAME, VALUE), where
        NAME is the name of the variable, and VALUE is a gdb.Value."""
        return

    @abstractmethod
    def child_count(self):
        """Return the number of children of this variable."""
        return

    def _compute_name(self, name):
        if name in self._by_name:
            self._name_counts[name] += 1
            name = name + " #" + str(self._name_counts[name])
        return name

    @in_gdb_thread
    def fetch_children(self, start, count):
        """Fetch children of this variable.
        START is the starting index.
        COUNT is the number to return, with 0 meaning return all.
        Returns an iterable of some kind."""
        if count == 0:
            count = self.child_count()
        if self._children is None:
            self._children = [None] * self.child_count()
        for idx in range(start, start + count):
            if idx >= len(self._children):
                break
            if self._children[idx] is None:
                name, value = self.fetch_one_child(idx)
                name = self._compute_name(name)
                var = VariableReference(name, value)
                self._children[idx] = var
                self._by_name[name] = var
            yield self._children[idx]

    @in_gdb_thread
    def find_child_by_name(self, name):
        """Find a child of this variable, given its name.
        Returns the value of the child, or throws if not found."""
        if name in self._by_name:
            return self._by_name[name]
        raise DAPException("no variable named '" + name + "'")


class VariableReference(BaseReference):
    """Concrete subclass of BaseReference that handles gdb.Value."""

    def __init__(self, name, value, result_name="value"):
        """Initializer.
        NAME is the name of this reference, see superclass.
        VALUE is a gdb.Value that holds the value.
        RESULT_NAME can be used to change how the simple string result
        is emitted in the result dictionary."""
        super().__init__(name)
        self._result_name = result_name
        self._value = value
        self._update_value()

    def _update_value(self):
        self.reset_children()
        self._printer = gdb.printing.make_visualizer(self._value)
        self._child_cache = None
        if self.has_children():
            self.count = -1
        else:
            self.count = None

    def assign(self, value):
        """Assign VALUE to this object and update."""
        self._value.assign(value)
        self._update_value()

    def has_children(self):
        return hasattr(self._printer, "children")

    def cache_children(self):
        if self._child_cache is None:
            self._child_cache = list(self._printer.children())
        return self._child_cache

    def child_count(self):
        if self.count is None:
            return None
        if self.count == -1:
            num_children = None
            if isinstance(self._printer, gdb.ValuePrinter) and hasattr(
                self._printer, "num_children"
            ):
                num_children = self._printer.num_children()
            if num_children is None:
                num_children = len(self.cache_children())
            self.count = num_children
        return self.count

    def to_object(self):
        result = super().to_object()
        result[self._result_name] = str(self._printer.to_string())
        num_children = self.child_count()
        if num_children is not None:
            if (
                hasattr(self._printer, "display_hint")
                and self._printer.display_hint() == "array"
            ):
                result["indexedVariables"] = num_children
            else:
                result["namedVariables"] = num_children
        if client_bool_capability("supportsMemoryReferences"):
            if (
                self._value.type.strip_typedefs().code == gdb.TYPE_CODE_PTR
                and not self._value.is_optimized_out
                and not self._value.is_unavailable
            ):
                result["memoryReference"] = hex(int(self._value))
        if client_bool_capability("supportsVariableType"):
            result["type"] = str(self._value.type)
        return result

    @in_gdb_thread
    def fetch_one_child(self, idx):
        if isinstance(self._printer, gdb.ValuePrinter) and hasattr(
            self._printer, "child"
        ):
            name, val = self._printer.child(idx)
        else:
            name, val = self.cache_children()[idx]
        if not isinstance(val, gdb.Value):
            val = gdb.Value(val)
        return (name, val)


@in_gdb_thread
def find_variable(ref):
    """Given a variable reference, return the corresponding variable object."""
    ref = ref - 1
    if ref < 0 or ref > len(all_variables):
        raise DAPException("invalid variablesReference")
    return all_variables[ref]
