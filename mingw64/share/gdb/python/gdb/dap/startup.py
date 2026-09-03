import functools
import queue
import sys
import threading
import traceback
from enum import IntEnum, auto
import gdb

if sys.version_info[0] == 3 and sys.version_info[1] <= 6:
    DAPQueue = queue.Queue
else:
    DAPQueue = queue.SimpleQueue
_gdb_thread = threading.current_thread()
_dap_thread = None


class DAPException(Exception):
    pass


def parse_and_eval(expression, global_context=False):
    try:
        return gdb.parse_and_eval(expression, global_context=global_context)
    except Exception as e:
        raise DAPException(str(e)) from e


def start_thread(name, target, args=()):
    """Start a new thread, invoking TARGET with *ARGS there.
    This is a helper function that ensures that any GDB signals are
    correctly blocked."""

    def thread_wrapper(*args):
        try:
            target(*args)
        except Exception as err:
            err_string = "%s, %s" % (err, type(err))
            thread_log("caught exception: " + err_string)
            log_stack()
        finally:
            thread_log("terminating")

    result = gdb.Thread(name=name, target=thread_wrapper, args=args, daemon=True)
    result.start()
    return result


def start_dap(target):
    """Start the DAP thread and invoke TARGET there."""
    exec_and_log("set breakpoint pending on")

    def really_start_dap():
        global _dap_thread
        _dap_thread = threading.current_thread()
        target()

    dap_thread = start_thread("DAP", really_start_dap)

    def _on_gdb_exiting(event):
        thread_log("joining DAP thread ...")
        dap_thread.join()
        thread_log("joining DAP thread done")

    gdb.events.gdb_exiting.connect(_on_gdb_exiting)


def in_gdb_thread(func):
    """A decorator that asserts that FUNC must be run in the GDB thread."""

    @functools.wraps(func)
    def ensure_gdb_thread(*args, **kwargs):
        assert threading.current_thread() is _gdb_thread
        return func(*args, **kwargs)

    return ensure_gdb_thread


def in_dap_thread(func):
    """A decorator that asserts that FUNC must be run in the DAP thread."""

    @functools.wraps(func)
    def ensure_dap_thread(*args, **kwargs):
        assert threading.current_thread() is _dap_thread
        return func(*args, **kwargs)

    return ensure_dap_thread


class LogLevel(IntEnum):
    DEFAULT = auto()
    FULL = auto()


class LogLevelParam(gdb.Parameter):
    """DAP logging level."""

    set_doc = "Set the DAP logging level."
    show_doc = "Show the DAP logging level."

    def __init__(self):
        super().__init__(
            "debug dap-log-level", gdb.COMMAND_MAINTENANCE, gdb.PARAM_ZUINTEGER
        )
        self.value = LogLevel.DEFAULT


_log_level = LogLevelParam()


class LoggingParam(gdb.Parameter):
    """Whether DAP logging is enabled."""

    set_doc = "Set the DAP logging status."
    show_doc = "Show the DAP logging status."
    lock = threading.Lock()
    log_file = None

    def __init__(self):
        super().__init__(
            "debug dap-log-file", gdb.COMMAND_MAINTENANCE, gdb.PARAM_OPTIONAL_FILENAME
        )
        self.value = None

    def get_set_string(self):
        with dap_log.lock:
            if self.log_file is not None:
                self.log_file.close()
                self.log_file = None
            if self.value is not None:
                self.log_file = open(self.value, "w")
        return ""


dap_log = LoggingParam()


def log(something, level=LogLevel.DEFAULT):
    """Log SOMETHING to the log file, if logging is enabled."""
    with dap_log.lock:
        if dap_log.log_file is not None and level <= _log_level.value:
            print(something, file=dap_log.log_file)
            dap_log.log_file.flush()


def thread_log(something, level=LogLevel.DEFAULT):
    """Log SOMETHING to the log file, if logging is enabled, and prefix
    the thread name."""
    if threading.current_thread() is _gdb_thread:
        thread_name = "GDB main"
    else:
        thread_name = threading.current_thread().name
    log(thread_name + ": " + something, level)


def log_stack(level=LogLevel.DEFAULT):
    """Log a stack trace to the log file, if logging is enabled."""
    with dap_log.lock:
        if dap_log.log_file is not None and level <= _log_level.value:
            traceback.print_exc(file=dap_log.log_file)
            dap_log.log_file.flush()


@in_gdb_thread
def exec_and_log(cmd, propagate_exception=False):
    """Execute the gdb command CMD.
    If logging is enabled, log the command and its output."""
    log("+++ " + cmd)
    try:
        output = gdb.execute(cmd, from_tty=True, to_string=True)
        if output != "":
            log(">>> " + output)
    except gdb.error as e:
        if propagate_exception:
            raise DAPException(str(e)) from e
        else:
            log_stack()


@in_gdb_thread
def exec_mi_and_log(*args):
    """Wrap gdb.execute_mi, logging the command."""
    log("+++ " + str(args))
    return gdb.execute_mi(*args)
