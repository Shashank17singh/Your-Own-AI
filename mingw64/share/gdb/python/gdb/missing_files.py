"""
MissingFileHandler base class, and support functions used by the
missing_debug.py and missing_objfile.py modules.
"""

import gdb


def isascii(ch):
    return ch.isascii()


def isalnum(ch):
    return ch.isalnum()


def _validate_name(name):
    """Validate a missing file handler name string.
    If name is valid as a missing file handler name, then this
    function does nothing.  If name is not valid then an exception is
    raised.
    Arguments:
        name: A string, the name of a missing file handler.
    Returns:
        Nothing.
    Raises:
        ValueError: If name is invalid as a missing file handler
                    name.
    """
    for ch in name:
        if not isascii(ch) or not (isalnum(ch) or ch in "_-"):
            raise ValueError(f"invalid character '{ch}' in handler name: {name}")


class MissingFileHandler:
    """Base class for missing file handlers written in Python.
    A missing file handler has a single method __call__ along with the
    read/write attribute enabled, and a read-only attribute name.  The
    attributes are provided by this class while the __call__ method is
    provided by a sub-class.  Each sub-classes __call__ method will
    have a different signature.
    Attributes:
        name: Read-only attribute, the name of this handler.
        enabled: When true this handler is enabled.
    """

    def __init__(self, name):
        """Constructor.
        Args:
            name: An identifying name for this handler.
        Raises:
            TypeError: name is not a string.
            ValueError: name contains invalid characters.
        """
        if not isinstance(name, str):
            raise TypeError(f"incorrect type for name: {type(name)}")
        _validate_name(name)
        self._name = name
        self._enabled = True

    @property
    def name(self):
        return self._name

    @property
    def enabled(self):
        return self._enabled

    @enabled.setter
    def enabled(self, value):
        if not isinstance(value, bool):
            raise TypeError(f"incorrect type for enabled attribute: {type(value)}")
        self._enabled = value


def register_handler(handler_type, locus, handler, replace=False):
    """Register handler in given locus.
    The handler is prepended to the locus's missing file handlers
    list. The name of handler should be unique (or replace must be
    True), and the name must pass the _validate_name check.
    Arguments:
        handler_type: A string, either 'debug' or 'objfile' indicating the
            type of handler to be registered.
        locus: Either a progspace, or None (in which case the unwinder
               is registered globally).
        handler: An object used as a missing file handler.  Usually a
            sub-class of MissingFileHandler.
        replace: If True, replaces existing handler with the same name
                 within locus.  Otherwise, raises RuntimeException if
                 unwinder with the same name already exists.
    Returns:
        Nothing.
    Raises:
        RuntimeError: The name of handler is not unique.
        TypeError: Bad locus type.
        AttributeError: Required attributes of handler are missing.
        ValueError: If the name of the handler is invalid, or if
            handler_type is neither 'debug' or 'objfile'.
    """
    if handler_type != "debug" and handler_type != "objfile":
        raise ValueError("handler_type must be 'debug' or 'objfile'")
    if locus is None:
        if gdb.parameter("verbose"):
            gdb.write(f"Registering global {handler.name} handler ...\n")
        locus = gdb
    elif isinstance(locus, gdb.Progspace):
        if gdb.parameter("verbose"):
            gdb.write(f"Registering {handler.name} handler for {locus.filename} ...\n")
    else:
        raise TypeError("locus should be gdb.Progspace or None")
    name = handler.name
    _validate_name(name)
    handler.enabled  # noqa: B018
    call_method = handler.__call__
    if not callable(call_method):
        raise AttributeError(  # noqa: TRY004
            f"'{type(handler).__name__}' object's '__call__' attribute is not callable"
        )
    i = 0
    for needle in locus.missing_file_handlers:
        if needle[0] == handler_type and needle[1].name == handler.name:
            if replace:
                del locus.missing_file_handlers[i]
            else:
                raise RuntimeError(f"Handler {handler.name} already exists.")
        i += 1  # noqa: SIM113
    locus.missing_file_handlers.insert(0, (handler_type, handler))
