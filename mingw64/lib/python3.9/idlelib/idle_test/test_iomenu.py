"Test , coverage 17%."

import unittest
from idlelib import iomenu
from idlelib.editor import EditorWindow
from tkinter import Tk

from test.support import requires


class IOBindingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        requires("gui")
        cls.root = Tk()
        cls.root.withdraw()
        cls.editwin = EditorWindow(root=cls.root)
        cls.io = iomenu.IOBinding(cls.editwin)

    @classmethod
    def tearDownClass(cls):
        cls.io.close()
        cls.editwin._close()
        del cls.editwin
        cls.root.update_idletasks()
        for id in cls.root.tk.call("after", "info"):
            cls.root.after_cancel(id)  # Need for EditorWindow.
        cls.root.destroy()
        del cls.root

    def test_init(self):
        self.assertIs(self.io.editwin, self.editwin)

    def test_fixnewlines_end(self):
        eq = self.assertEqual
        io = self.io
        fix = io.fixnewlines
        text = io.editwin.text
        self.editwin.interp = None
        eq(fix(), "")
        del self.editwin.interp
        text.insert(1.0, "a")
        eq(fix(), "a" + io.eol_convention)
        eq(text.get("1.0", "end-1c"), "a\n")
        eq(fix(), "a" + io.eol_convention)


if __name__ == "__main__":
    unittest.main(verbosity=2)
