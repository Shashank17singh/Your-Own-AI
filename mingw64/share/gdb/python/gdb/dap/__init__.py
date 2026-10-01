import os

from . import (
    breakpoint,  # noqa: F401
    bt,  # noqa: F401
    completions,  # noqa: F401
    disassemble,  # noqa: F401
    evaluate,  # noqa: F401
    launch,  # noqa: F401
    locations,  # noqa: F401
    memory,  # noqa: F401
    modules,  # noqa: F401
    next,  # noqa: F401
    pause,  # noqa: F401
    scopes,  # noqa: F401
    sources,  # noqa: F401
    startup,
    threads,  # noqa: F401
)
from .server import Server


def run():
    """Main entry point for the DAP server.
    This is called by the GDB DAP interpreter."""
    startup.exec_and_log("set python print-stack full")
    startup.exec_and_log("set pagination off")
    saved_out = os.dup(1)
    saved_in = os.dup(0)
    os.set_inheritable(saved_out, False)
    os.set_inheritable(saved_in, False)
    new_in = os.open(os.devnull, os.O_RDONLY)
    os.dup2(new_in, 0, True)
    os.close(new_in)
    rfd, wfd = os.pipe()
    os.set_inheritable(rfd, False)
    os.dup2(wfd, 1, True)
    os.dup2(wfd, 2, True)
    os.close(wfd)
    global server
    server = Server(open(saved_in, "rb"), open(saved_out, "wb"), open(rfd, "r"))


session_started = False


def pre_command_loop():
    """DAP's pre_command_loop interpreter hook.  This is called by the GDB DAP
    interpreter."""
    global session_started
    if not session_started:
        session_started = True
        startup.thread_log("starting DAP server")
        startup.exec_and_log("show version")
        startup.exec_and_log("show configuration")
        startup.start_dap(server.main_loop)
