import gdb


class _AsString(gdb.Function):
    """Return the string representation of a value.
    Usage: $_as_string (VALUE)
    Arguments:
      VALUE: any value
    Returns:
      The string representation of the value."""

    def __init__(self):
        super(_AsString, self).__init__("_as_string")

    def invoke(self, val):
        return str(val)


_AsString()
