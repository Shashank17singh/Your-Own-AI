from .events import exec_and_expect_stop
from .server import request


@request("pause", response=False, expect_stopped=False)
def pause(**args):
    exec_and_expect_stop("interrupt -a", True)
