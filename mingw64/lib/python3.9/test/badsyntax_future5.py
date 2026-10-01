"""This is a test"""


def f(x):
    def g(y):
        return x + y

    return g


result = f(2)(4)
