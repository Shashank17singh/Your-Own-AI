import gdb
from .server import request
from .startup import in_gdb_thread


@in_gdb_thread
def _thread_name(thr):
    if thr.name is not None:
        return thr.name
    if thr.details is not None:
        return thr.details
    return f"Thread #{thr.num}"


@request("threads", expect_stopped=False)
def threads(**args):
    result = []
    for thr in gdb.selected_inferior().threads():
        result.append(
            {
                "id": thr.global_num,
                "name": _thread_name(thr),
            }
        )
    return {
        "threads": result,
    }
