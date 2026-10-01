"""Do a minimal test of all the modules that aren't otherwise tested."""

import importlib
import platform
import sys
import unittest

from test import support


class TestUntestedModules(unittest.TestCase):
    def test_untested_modules_can_be_imported(self):
        untested = ("encodings", "formatter")
        with support.check_warnings(quiet=True):
            for name in untested:
                try:
                    support.import_module(f"test.test_{name}")
                except unittest.SkipTest:
                    importlib.import_module(name)
                else:
                    self.fail(
                        f"{name} has tests even though test_sundry claims otherwise"
                    )

            if sys.platform.startswith("win") and not platform.win32_is_iot():
                pass

            try:
                import tty  # Not available on Windows
            except ImportError:
                if support.verbose:
                    print("skipping tty")


if __name__ == "__main__":
    unittest.main()
