from .startup import exec_and_log, in_gdb_thread, log


@in_gdb_thread
def set_thread(thread_id):
    """Set the current thread to THREAD_ID."""
    if thread_id == 0:
        log("+++ Thread == 0 +++")
    else:
        exec_and_log("thread " + str(thread_id))
