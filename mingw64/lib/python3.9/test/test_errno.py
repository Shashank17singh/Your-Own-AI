"""Test the errno module
Roger E. Masse
"""

import errno
import unittest

std_c_errors = frozenset(["EDOM", "ERANGE"])


class ErrnoAttributeTests(unittest.TestCase):
    def test_for_improper_attributes(self):
        # No unexpected attributes should be on the module.
        for error_code in std_c_errors:
            self.assertTrue(
                hasattr(errno, error_code), f"errno is missing {error_code}"
            )

    def test_using_errorcode(self):
        # Every key value in errno.errorcode should be on the module.
        for value in errno.errorcode.values():
            self.assertTrue(hasattr(errno, value), f"no {value} attr in errno")


class ErrorcodeTests(unittest.TestCase):
    def test_attributes_in_errorcode(self):
        for attribute in errno.__dict__:
            if attribute.isupper():
                self.assertIn(
                    getattr(errno, attribute),
                    errno.errorcode,
                    f"no {attribute} attr in errno.errorcode",
                )


if __name__ == "__main__":
    unittest.main()
