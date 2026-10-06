"""Tests for distutils.command.bdist_msi."""

import sys
import unittest
from distutils.tests import support

from test.support import check_warnings, run_unittest


@unittest.skipUnless(sys.platform == "win32", "these tests require Windows")
class BDistMSITestCase(
    support.TempdirManager, support.LoggingSilencer, unittest.TestCase
):
    def test_minimal(self):
        # minimal test XXX need more tests
        from distutils.command.bdist_msi import bdist_msi

        _project_dir, dist = self.create_dist()
        with check_warnings(("", DeprecationWarning)):
            cmd = bdist_msi(dist)
        cmd.ensure_finalized()


def test_suite():
    return unittest.makeSuite(BDistMSITestCase)


if __name__ == "__main__":
    run_unittest(test_suite())
