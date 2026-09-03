import gdb
from .events import exec_and_expect_stop
from .server import capability, request
from .startup import in_gdb_thread
from .state import set_thread


@in_gdb_thread
def _handle_thread_step(thread_id, single_thread, select=False):
    set_thread(thread_id)
    if single_thread:
        result = True
        arg = "on"
    else:
        result = False
        arg = "off"
    try:
        gdb.execute("set scheduler-locking " + arg, from_tty=True, to_string=True)
    except gdb.error:
        result = False
    if select:
        gdb.newest_frame().select()
    return result


@request("next", response=False)
def next(
    *, threadId: int, singleThread: bool = False, granularity: str = "statement", **args
):
    _handle_thread_step(threadId, singleThread)
    cmd = "next"
    if granularity == "instruction":
        cmd += "i"
    exec_and_expect_stop(cmd)


@capability("supportsSteppingGranularity")
@capability("supportsSingleThreadExecutionRequests")
@request("stepIn", response=False)
def step_in(
    *, threadId: int, singleThread: bool = False, granularity: str = "statement", **args
):
    _handle_thread_step(threadId, singleThread)
    cmd = "step"
    if granularity == "instruction":
        cmd += "i"
    exec_and_expect_stop(cmd)


@request("stepOut")
def step_out(*, threadId: int, singleThread: bool = False, **args):
    _handle_thread_step(threadId, singleThread, True)
    exec_and_expect_stop("finish &", propagate_exception=True)


@request("continue")
def continue_request(*, threadId: int, singleThread: bool = False, **args):
    locked = _handle_thread_step(threadId, singleThread)
    exec_and_expect_stop("continue &")
    return {"allThreadsContinued": not locked}
