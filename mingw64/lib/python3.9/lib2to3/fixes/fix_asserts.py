"""Fixer that replaces deprecated unittest method names."""

# Author: Ezio Melotti

from ..fixer_base import BaseFix
from ..fixer_util import Name

NAMES = {
    "assert_": "assertTrue",
    "assertEquals": "assertEqual",
    "assertNotEquals": "assertNotEqual",
    "assertAlmostEquals": "assertAlmostEqual",
    "assertNotAlmostEquals": "assertNotAlmostEqual",
    "assertRegexpMatches": "assertRegex",
    "assertRaisesRegexp": "assertRaisesRegex",
    "failUnlessEqual": "assertEqual",
    "failIfEqual": "assertNotEqual",
    "failUnlessAlmostEqual": "assertAlmostEqual",
    "failIfAlmostEqual": "assertNotAlmostEqual",
    "failUnless": "assertTrue",
    "failUnlessRaises": "assertRaises",
    "failIf": "assertFalse",
}


class FixAsserts(BaseFix):
    PATTERN = """
              power< any+ trailer< '.' meth=({})> any* >
              """.format("|".join(map(repr, NAMES)))

    def transform(self, node, results):
        name = results["meth"][0]
        name.replace(Name(NAMES[str(name)], prefix=name.prefix))
