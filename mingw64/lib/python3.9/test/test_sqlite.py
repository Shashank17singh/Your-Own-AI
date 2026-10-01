import test.support

# Skip test if _sqlite3 module not installed
test.support.import_module("_sqlite3")

import sqlite3
import unittest
from sqlite3.test import (
    backup,
    dbapi,
    dump,
    factory,
    hooks,
    regression,
    transactions,
    types,
    userfunctions,
)


def load_tests(*args):
    if test.support.verbose:
        print(
            "test_sqlite: testing with version",
            f"{sqlite3.version!r}, sqlite_version {sqlite3.sqlite_version!r}",
        )
    return unittest.TestSuite(
        [
            dbapi.suite(),
            types.suite(),
            userfunctions.suite(),
            factory.suite(),
            transactions.suite(),
            hooks.suite(),
            regression.suite(),
            dump.suite(),
            backup.suite(),
        ]
    )


if __name__ == "__main__":
    unittest.main()
