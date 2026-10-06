#
# test_codecmaps_jp.py
#   Codec mapping tests for Japanese encodings
#

import unittest

from test import multibytecodec_support


class TestCP932Map(multibytecodec_support.TestBase_Mapping, unittest.TestCase):
    encoding = "cp932"
    mapfileurl = "http://www.pythontest.net/unicode/CP932.TXT"
    supmaps = [  # noqa: RUF012
        (b"\x80", "\u0080"),
        (b"\xa0", "\uf8f0"),
        (b"\xfd", "\uf8f1"),
        (b"\xfe", "\uf8f2"),
        (b"\xff", "\uf8f3"),
    ]
    for i in range(0xA1, 0xE0):
        supmaps.append((bytes([i]), chr(i + 0xFEC0)))


class TestEUCJPCOMPATMap(multibytecodec_support.TestBase_Mapping, unittest.TestCase):
    encoding = "euc_jp"
    mapfilename = "EUC-JP.TXT"
    mapfileurl = "http://www.pythontest.net/unicode/EUC-JP.TXT"


class TestSJISCOMPATMap(multibytecodec_support.TestBase_Mapping, unittest.TestCase):
    encoding = "shift_jis"
    mapfilename = "SHIFTJIS.TXT"
    mapfileurl = "http://www.pythontest.net/unicode/SHIFTJIS.TXT"
    pass_enctest = [  # noqa: RUF012
        (b"\x81_", "\\"),
    ]
    pass_dectest = [  # noqa: RUF012
        (b"\\", "\xa5"),
        (b"~", "\u203e"),
        (b"\x81_", "\\"),
    ]


class TestEUCJISX0213Map(multibytecodec_support.TestBase_Mapping, unittest.TestCase):
    encoding = "euc_jisx0213"
    mapfilename = "EUC-JISX0213.TXT"
    mapfileurl = "http://www.pythontest.net/unicode/EUC-JISX0213.TXT"


class TestSJISX0213Map(multibytecodec_support.TestBase_Mapping, unittest.TestCase):
    encoding = "shift_jisx0213"
    mapfilename = "SHIFT_JISX0213.TXT"
    mapfileurl = "http://www.pythontest.net/unicode/SHIFT_JISX0213.TXT"


if __name__ == "__main__":
    unittest.main()
