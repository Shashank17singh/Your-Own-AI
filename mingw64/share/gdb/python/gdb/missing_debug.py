"""
MissingDebugHandler base class, and register_handler function.
"""

import gdb
from gdb.missing_files import MissingFileHandler


class MissingDebugHandler(MissingFileHandler):
    """Base class for missing debug handlers written in Python.
    A missing debug handler has a single method __call__ along with
    the read/write attribute enabled, and a read-only attribute name.
    Attributes:
        name: Read-only attribute, the name of this handler.
        enabled: When true this handler is enabled.
    """

    def __call__(self, objfile):
        """Handle missing debug information for an objfile.
        Arguments:
            objfile: A gdb.Objfile for which GDB could not find any
                debug information.
        Returns:
            True: GDB should try again to locate the debug information
                for objfile, the handler may have installed the
                missing information.
            False: GDB should move on without the debug information
                for objfile.
            A string: GDB should load the file at the given path; it
                contains the debug information for objfile.
            None: This handler can't help with objfile.  GDB should
                try any other registered handlers.
        """
        raise NotImplementedError("MissingDebugHandler.__call__()")


def register_handler(locus, handler, replace=False):
    """See gdb.missing_files.register_handler."""
    gdb.missing_files.register_handler("debug", locus, handler, replace)
