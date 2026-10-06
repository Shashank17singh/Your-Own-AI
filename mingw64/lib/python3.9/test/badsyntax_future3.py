"""This is a test"""

from __future__ import rested_snopes  # noqa: F407


def f(x):
    def g(y):
        return x + y

    return g


result = f(2)(4)
