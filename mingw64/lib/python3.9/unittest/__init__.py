"""
Python unit testing framework, based on Erich Gamma's JUnit and Kent Beck's
Smalltalk testing framework (used with permission).
This module contains the core framework classes that form the basis of
specific test cases and suites (TestCase, TestSuite etc.), and also a
text-based utility class for running the tests and reporting the results
 (TextTestRunner).
Simple usage:
    import unittest
    class IntegerArithmeticTestCase(unittest.TestCase):
        def testAdd(self):  # test method names begin with 'test'
            self.assertEqual((1 + 2), 3)
            self.assertEqual(0 + 1, 1)
        def testMultiply(self):
            self.assertEqual((0 * 10), 0)
            self.assertEqual((5 * 8), 40)
    if __name__ == '__main__':
        unittest.main()
Further information is available in the bundled documentation, and from
  http://docs.python.org/library/unittest.html
Copyright (c) 1999-2003 Steve Purcell
Copyright (c) 2003-2010 Python Software Foundation
This module is free software, and you may redistribute it and/or modify
it under the same terms as Python itself, so long as this copyright message
and disclaimer are retained in their original form.
IN NO EVENT SHALL THE AUTHOR BE LIABLE TO ANY PARTY FOR DIRECT, INDIRECT,
SPECIAL, INCIDENTAL, OR CONSEQUENTIAL DAMAGES ARISING OUT OF THE USE OF
THIS CODE, EVEN IF THE AUTHOR HAS BEEN ADVISED OF THE POSSIBILITY OF SUCH
DAMAGE.
THE AUTHOR SPECIFICALLY DISCLAIMS ANY WARRANTIES, INCLUDING, BUT NOT
LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A
PARTICULAR PURPOSE.  THE CODE PROVIDED HEREUNDER IS ON AN "AS IS" BASIS,
AND THERE IS NO OBLIGATION WHATSOEVER TO PROVIDE MAINTENANCE,
SUPPORT, UPDATES, ENHANCEMENTS, OR MODIFICATIONS.
"""

__all__ = [
    "FunctionTestCase",
    "IsolatedAsyncioTestCase",
    "SkipTest",
    "TestCase",
    "TestLoader",
    "TestResult",
    "TestSuite",
    "TextTestResult",
    "TextTestRunner",
    "addModuleCleanup",
    "defaultTestLoader",
    "expectedFailure",
    "installHandler",
    "main",
    "registerResult",
    "removeHandler",
    "removeResult",
    "skip",
    "skipIf",
    "skipUnless",
]
__all__.extend(["findTestCases", "getTestCaseNames", "makeSuite"])
__unittest = True
from .case import (
    FunctionTestCase,
    SkipTest,
    TestCase,
    addModuleCleanup,
    expectedFailure,
    skip,
    skipIf,
    skipUnless,
)
from .loader import (
    TestLoader,
    defaultTestLoader,
    findTestCases,  # noqa: F401
    getTestCaseNames,  # noqa: F401
    makeSuite,  # noqa: F401
)
from .main import TestProgram, main  # noqa: F401
from .result import TestResult
from .runner import TextTestResult, TextTestRunner
from .signals import installHandler, registerResult, removeHandler, removeResult
from .suite import BaseTestSuite, TestSuite  # noqa: F401

_TextTestResult = TextTestResult


def load_tests(loader, tests, pattern):
    import os.path

    this_dir = os.path.dirname(__file__)
    return loader.discover(start_dir=this_dir, pattern=pattern)


def __dir__():
    return globals().keys() | {"IsolatedAsyncioTestCase"}


def __getattr__(name):
    if name == "IsolatedAsyncioTestCase":
        global IsolatedAsyncioTestCase
        from .async_case import IsolatedAsyncioTestCase

        return IsolatedAsyncioTestCase
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
