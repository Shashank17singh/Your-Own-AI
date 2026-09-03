import re
from typing import Mapping, Optional, Sequence
import gdb
from .events import exec_and_expect_stop, expect_process, expect_stop
from .server import (
    DeferredRequest,
    call_function_later,
    capability,
    request,
    send_gdb,
    send_gdb_with_response,
)
from .startup import DAPException, exec_and_log, in_dap_thread, in_gdb_thread

_launch_or_attach_promise = None


class _LaunchOrAttachDeferredRequest(DeferredRequest):
    def __init__(self, callback):
        self._callback = callback
        global _launch_or_attach_promise
        if _launch_or_attach_promise is not None:
            raise DAPException("launch or attach already specified")
        _launch_or_attach_promise = self

    @in_dap_thread
    def invoke(self):
        return self._callback()

    @in_dap_thread
    def reschedule(self):
        global _launch_or_attach_promise
        _launch_or_attach_promise = None
        super().reschedule()


@in_gdb_thread
def file_command(program):
    program = re.sub("[ \t\n\r\f\v\\\\'\"]", "\\\\\\g<0>", program)
    exec_and_log("file " + program)


@request("launch", on_dap_thread=True)
def launch(
    *,
    program: Optional[str] = None,
    cwd: Optional[str] = None,
    args: Sequence[str] = (),
    env: Optional[Mapping[str, str]] = None,
    stopAtBeginningOfMainSubprogram: bool = False,
    stopOnEntry: bool = False,
    **extra,
):
    @in_gdb_thread
    def _setup_launch():
        if cwd is not None:
            exec_and_log("cd " + cwd)
        if program is not None:
            file_command(program)
        inf = gdb.selected_inferior()
        inf.arguments = args
        if env is not None:
            inf.clear_env()
            for name, value in env.items():
                inf.set_env(name, value)

    @in_gdb_thread
    def _do_launch():
        expect_process("process")
        if stopAtBeginningOfMainSubprogram:
            cmd = "start"
        elif stopOnEntry:
            cmd = "starti"
        else:
            cmd = "run"
        exec_and_expect_stop(cmd)

    @in_dap_thread
    def _launch_impl():
        send_gdb_with_response(_setup_launch)
        send_gdb(_do_launch)
        return None

    return _LaunchOrAttachDeferredRequest(_launch_impl)


@request("attach", on_dap_thread=True)
def attach(
    *,
    program: Optional[str] = None,
    pid: Optional[int] = None,
    target: Optional[str] = None,
    **args,
):
    @in_gdb_thread
    def _do_attach():
        if program is not None:
            file_command(program)
        if pid is not None:
            cmd = "attach " + str(pid)
        elif target is not None:
            cmd = "target remote " + target
        else:
            raise DAPException("attach requires either 'pid' or 'target'")
        expect_process("attach")
        expect_stop("attach")
        exec_and_log(cmd)
        return None

    @in_dap_thread
    def _attach_impl():
        return send_gdb_with_response(_do_attach)

    return _LaunchOrAttachDeferredRequest(_attach_impl)


@capability("supportsConfigurationDoneRequest")
@request("configurationDone", on_dap_thread=True)
def config_done(**args):
    if _launch_or_attach_promise is None:
        raise DAPException("launch or attach not specified")
    call_function_later(_launch_or_attach_promise.reschedule)
