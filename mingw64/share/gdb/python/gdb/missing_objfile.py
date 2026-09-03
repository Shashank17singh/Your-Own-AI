"""
MissingObjfileHandler base class, and register_handler function.
"""

import gdb
from gdb.missing_files import MissingFileHandler


class MissingObjfileHandler(MissingFileHandler):
    """Base class for missing objfile handlers written in Python.
    A missing objfile handler has a single method __call__ along with
    the read/write attribute enabled, and a read-only attribute name.
    Attributes:
        name: Read-only attribute, the name of this handler.
        enabled: When true this handler is enabled.
    """

    def __call__(self, buildid, filename):
        """Handle a missing objfile when GDB can knows the build-id.
        Arguments:
            buildid: A string containing the build-id for the objfile
                GDB is searching for.
            filename: A string containing the name of the file GDB is
                searching for.  This is provided only for the purpose
                of creating diagnostic messages.  If the file is found
                it does not have to be placed here, and this file
                might already exist but GDB has determined it is not
                suitable for use, e.g. if the build-id doesn't match.
        Returns:
            True: GDB should try again to locate the missing objfile,
                the handler may have installed the missing file.
            False: GDB should move on without the objfile.  The
                handler has determined that this objfile is not
                available.
            A string: GDB should load the file at the given path; it
                contains the requested objfile.
            None: This handler can't help with this objfile.  GDB
                should try any other registered handlers.
        """
        raise NotImplementedError("MissingObjfileHandler.__call__()")


def register_handler(locus, handler, replace=False):
    """See gdb.missing_files.register_handler."""
    gdb.missing_files.register_handler("objfile", locus, handler, replace)
