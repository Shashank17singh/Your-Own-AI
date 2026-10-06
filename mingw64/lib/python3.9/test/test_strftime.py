"""
Unittest for time.strftime
"""

import calendar
import re
import sys
import time
import unittest

from test import support


# helper functions
def fixasctime(s):
    if s[8] == " ":
        s = s[:8] + "0" + s[9:]
    return s


def escapestr(text, ampm):
    """
    Escape text to deal with possible locale values that have regex
    syntax while allowing regex syntax used for comparison.
    """
    new_text = re.escape(text)
    new_text = new_text.replace(re.escape(ampm), ampm)
    new_text = new_text.replace(r"\%", "%")
    new_text = new_text.replace(r"\:", ":")
    new_text = new_text.replace(r"\?", "?")
    return new_text


class StrftimeTest(unittest.TestCase):
    def _update_variables(self, now):
        # we must update the local variables on every cycle
        self.gmt = time.gmtime(now)
        now = time.localtime(now)

        if now[3] < 12:
            self.ampm = "(AM|am)"
        else:
            self.ampm = "(PM|pm)"

        self.jan1 = time.localtime(time.mktime((now[0], 1, 1, 0, 0, 0, 0, 1, 0)))

        try:
            if now[8]:
                self.tz = time.tzname[1]
            else:
                self.tz = time.tzname[0]
        except AttributeError:
            self.tz = ""

        if now[3] > 12:
            self.clock12 = now[3] - 12
        elif now[3] > 0:
            self.clock12 = now[3]
        else:
            self.clock12 = 12

        self.now = now

    def setUp(self):
        try:
            import java

            java.util.Locale.setDefault(java.util.Locale.US)
        except ImportError:
            from locale import LC_TIME, setlocale

            saved_locale = setlocale(LC_TIME)
            setlocale(LC_TIME, "C")
            self.addCleanup(setlocale, LC_TIME, saved_locale)

    def test_strftime(self):
        now = time.time()
        self._update_variables(now)
        self.strftest1(now)
        self.strftest2(now)

        if support.verbose:
            print(
                f"Strftime test, platform: {sys.platform}, Python version: {sys.version.split()[0]}"
            )

        for j in range(-5, 5):
            for i in range(25):
                arg = now + (i + j * 100) * 23 * 3603
                self._update_variables(arg)
                self.strftest1(arg)
                self.strftest2(arg)

    def strftest1(self, now):
        if support.verbose:
            print("strftime test for", time.ctime(now))
        now = self.now
        # Make sure any characters that could be taken as regex syntax is
        # escaped in escapestr()
        expectations = (
            ("%a", calendar.day_abbr[now[6]], "abbreviated weekday name"),
            ("%A", calendar.day_name[now[6]], "full weekday name"),
            ("%b", calendar.month_abbr[now[1]], "abbreviated month name"),
            ("%B", calendar.month_name[now[1]], "full month name"),
            # %c see below
            ("%d", "%02d" % now[2], "day of month as number (00-31)"),  # noqa: UP031
            ("%H", "%02d" % now[3], "hour (00-23)"),  # noqa: UP031
            ("%I", "%02d" % self.clock12, "hour (01-12)"),  # noqa: UP031
            ("%j", "%03d" % now[7], "julian day (001-366)"),  # noqa: UP031
            ("%m", "%02d" % now[1], "month as number (01-12)"),  # noqa: UP031
            ("%M", "%02d" % now[4], "minute, (00-59)"),  # noqa: UP031
            ("%p", self.ampm, "AM or PM as appropriate"),
            ("%S", "%02d" % now[5], "seconds of current time (00-60)"),  # noqa: UP031
            (
                "%U",
                "%02d" % ((now[7] + self.jan1[6]) // 7),  # noqa: UP031
                "week number of the year (Sun 1st)",
            ),
            ("%w", "0?%d" % ((1 + now[6]) % 7), "weekday as a number (Sun 1st)"),  # noqa: UP031
            (
                "%W",
                "%02d" % ((now[7] + (self.jan1[6] - 1) % 7) // 7),  # noqa: UP031
                "week number of the year (Mon 1st)",
            ),
            # %x see below
            ("%X", "%02d:%02d:%02d" % (now[3], now[4], now[5]), "%H:%M:%S"),  # noqa: UP031
            ("%y", "%02d" % (now[0] % 100), "year without century"),  # noqa: UP031
            ("%Y", "%d" % now[0], "year with century"),  # noqa: UP031
            # %Z see below
            ("%%", "%", "single percent sign"),
        )

        for e in expectations:
            # musn't raise a value error
            try:
                result = time.strftime(e[0], now)
            except ValueError as error:
                self.fail(f"strftime '{e[0]}' format gave error: {error}")
            if re.match(escapestr(e[1], self.ampm), result):
                continue
            if not result or result[0] == "%":
                self.fail(
                    f"strftime does not support standard '{e[0]}' format ({e[2]})"
                )
            else:
                self.fail(
                    f"Conflict for {e[0]} ({e[2]}): expected {e[1]}, but got {result}"
                )

    def strftest2(self, now):
        nowsecs = str(int(now))[:-1]
        now = self.now

        nonstandard_expectations = (
            # These are standard but don't have predictable output
            ("%c", fixasctime(time.asctime(now)), "near-asctime() format"),
            (
                "%x",
                "%02d/%02d/%02d" % (now[1], now[2], (now[0] % 100)),  # noqa: UP031
                "%m/%d/%y %H:%M:%S",
            ),
            ("%Z", f"{self.tz}", "time zone name"),
            # These are some platform specific extensions
            ("%D", "%02d/%02d/%02d" % (now[1], now[2], (now[0] % 100)), "mm/dd/yy"),  # noqa: UP031
            ("%e", "%2d" % now[2], "day of month as number, blank padded ( 0-31)"),  # noqa: UP031
            ("%h", calendar.month_abbr[now[1]], "abbreviated month name"),
            ("%k", "%2d" % now[3], "hour, blank padded ( 0-23)"),  # noqa: UP031
            ("%n", "\n", "newline character"),
            (
                "%r",
                "%02d:%02d:%02d %s" % (self.clock12, now[4], now[5], self.ampm),  # noqa: UP031
                "%I:%M:%S %p",
            ),
            ("%R", "%02d:%02d" % (now[3], now[4]), "%H:%M"),  # noqa: UP031
            ("%s", nowsecs, "seconds since the Epoch in UCT"),
            ("%t", "\t", "tab character"),
            ("%T", "%02d:%02d:%02d" % (now[3], now[4], now[5]), "%H:%M:%S"),  # noqa: UP031
            (
                "%3y",
                "%03d" % (now[0] % 100),  # noqa: UP031
                "year without century rendered using fieldwidth",
            ),
        )

        for e in nonstandard_expectations:
            try:
                result = time.strftime(e[0], now)
            except ValueError as result:
                msg = f"Error for nonstandard '{e[0]}' format ({e[2]}): {result!s}"
                if support.verbose:
                    print(msg)
                continue
            if re.match(escapestr(e[1], self.ampm), result):
                if support.verbose:
                    print(f"Supports nonstandard '{e[0]}' format ({e[2]})")
            elif not result or result[0] == "%":
                if support.verbose:
                    print(f"Does not appear to support '{e[0]}' format ({e[2]})")
            else:
                if support.verbose:
                    print(f"Conflict for nonstandard '{e[0]}' format ({e[2]}):")
                    print(f"  Expected {e[1]}, but got {result}")


class Y1900Tests(unittest.TestCase):
    """A limitation of the MS C runtime library is that it crashes if
    a date before 1900 is passed with a format string containing "%y"
    """

    def test_y_before_1900(self):
        # Issue #13674, #19634
        t = (1899, 1, 1, 0, 0, 0, 0, 0, 0)
        if sys.platform == "win32" or sys.platform.startswith(
            ("aix", "sunos", "solaris")
        ):
            with self.assertRaises(ValueError):
                time.strftime("%y", t)
        else:
            self.assertEqual(time.strftime("%y", t), "99")

    def test_y_1900(self):
        self.assertEqual(time.strftime("%y", (1900, 1, 1, 0, 0, 0, 0, 0, 0)), "00")

    def test_y_after_1900(self):
        self.assertEqual(time.strftime("%y", (2013, 1, 1, 0, 0, 0, 0, 0, 0)), "13")


if __name__ == "__main__":
    unittest.main()
