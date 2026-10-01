"Test debugger, coverage 19%"

import unittest
from idlelib import debugger

from test.support import requires

requires("gui")
from tkinter import Tk


class NameSpaceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Tk()
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()
        del cls.root

    def test_init(self):
        debugger.NamespaceViewer(self.root, "Test")


# Other classes are Idb, Debugger, and StackViewer.

if __name__ == "__main__":
    unittest.main(verbosity=2)
