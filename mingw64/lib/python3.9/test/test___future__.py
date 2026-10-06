import __future__

import unittest

GOOD_SERIALS = ("alpha", "beta", "candidate", "final")

features = __future__.all_feature_names


class FutureTest(unittest.TestCase):
    def test_names(self):
        # Verify that all_feature_names appears correct.
        given_feature_names = features[:]
        for name in dir(__future__):
            obj = getattr(__future__, name, None)
            if obj is not None and isinstance(obj, __future__._Feature):
                self.assertTrue(
                    name in given_feature_names,
                    f"{name!r} should have been in all_feature_names",
                )
                given_feature_names.remove(name)
        self.assertEqual(
            len(given_feature_names),
            0,
            f"all_feature_names has too much: {given_feature_names!r}",
        )

    def test_attributes(self):
        for feature in features:
            value = getattr(__future__, feature)

            optional = value.getOptionalRelease()
            mandatory = value.getMandatoryRelease()

            a = self.assertTrue
            e = self.assertEqual

            def check(t, name):
                a(isinstance(t, tuple), f"{name} isn't tuple")  # noqa: B023
                e(len(t), 5, f"{name} isn't 5-tuple")  # noqa: B023
                major, minor, micro, level, serial = t
                a(isinstance(major, int), f"{name} major isn't int")  # noqa: B023
                a(isinstance(minor, int), f"{name} minor isn't int")  # noqa: B023
                a(isinstance(micro, int), f"{name} micro isn't int")  # noqa: B023
                a(isinstance(level, str), f"{name} level isn't string")  # noqa: B023
                a(level in GOOD_SERIALS, f"{name} level string has unknown value")  # noqa: B023
                a(isinstance(serial, int), f"{name} serial isn't int")  # noqa: B023

            check(optional, "optional")
            if mandatory is not None:
                check(mandatory, "mandatory")
                a(
                    optional < mandatory,
                    "optional not less than mandatory, and mandatory not None",
                )

            a(
                hasattr(value, "compiler_flag"),
                "feature is missing a .compiler_flag attr",
            )
            # Make sure the compile accepts the flag.
            compile("", "<test>", "exec", value.compiler_flag)
            a(
                isinstance(value.compiler_flag, int),
                ".compiler_flag isn't int",
            )


if __name__ == "__main__":
    unittest.main()
