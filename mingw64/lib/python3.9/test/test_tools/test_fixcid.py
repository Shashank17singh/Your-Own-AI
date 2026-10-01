"""Test Tools/scripts/fixcid.py."""

import os
import os.path
import runpy
import sys
import unittest
from io import StringIO

from test import support
from test.test_tools import scriptsdir, skip_if_missing

skip_if_missing()


class Test(unittest.TestCase):
    def test_parse_strings(self):
        old1 = 'int xx = "xx\\"xx"[xx];\n'
        old2 = "int xx = 'x\\'xx' + xx;\n"
        output = self.run_script(old1 + old2)
        new1 = 'int yy = "xx\\"xx"[yy];\n'
        new2 = "int yy = 'x\\'xx' + yy;\n"
        self.assertMultiLineEqual(
            output,
            f"1\n< {old1}> {new1}{new1}2\n< {old2}> {new2}{new2}",
        )

    def test_alter_comments(self):
        output = self.run_script(
            substfile="xx yy\n*aa bb\n",
            args=(
                "-c",
                "-",
            ),
            input="/* xx altered */\nint xx;\n/* aa unaltered */\nint aa;\n",
        )
        self.assertMultiLineEqual(
            output,
            "1\n"
            "< /* xx altered */\n"
            "> /* yy altered */\n"
            "/* yy altered */\n"
            "2\n"
            "< int xx;\n"
            "> int yy;\n"
            "int yy;\n"
            "/* aa unaltered */\n"
            "4\n"
            "< int aa;\n"
            "> int bb;\n"
            "int bb;\n",
        )

    def test_directory(self):
        os.mkdir(support.TESTFN)
        self.addCleanup(support.rmtree, support.TESTFN)
        c_filename = os.path.join(support.TESTFN, "file.c")
        with open(c_filename, "w") as file:
            file.write("int xx;\n")
        with open(os.path.join(support.TESTFN, "file.py"), "w") as file:
            file.write("xx = 'unaltered'\n")
        script = os.path.join(scriptsdir, "fixcid.py")
        output = self.run_script(args=(support.TESTFN,))
        self.assertMultiLineEqual(output, f"{c_filename}:\n1\n< int xx;\n> int yy;\n")

    def run_script(self, input="", *, args=("-",), substfile="xx yy\n"):
        substfilename = support.TESTFN + ".subst"
        with open(substfilename, "w") as file:
            file.write(substfile)
        self.addCleanup(support.unlink, substfilename)
        argv = ["fixcid.py", "-s", substfilename] + list(args)
        script = os.path.join(scriptsdir, "fixcid.py")
        with (
            support.swap_attr(sys, "argv", argv),
            support.swap_attr(sys, "stdin", StringIO(input)),
            support.captured_stdout() as output,
            support.captured_stderr(),
        ):
            try:
                runpy.run_path(script, run_name="__main__")
            except SystemExit as exit:
                self.assertEqual(exit.code, 0)
        return output.getvalue()
