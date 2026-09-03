from typing import Optional
import gdb
from .frames import dap_frame_generator
from .modules import module_id
from .scopes import symbol_value
from .server import capability, export_line, request
from .sources import make_source
from .startup import in_gdb_thread
from .state import set_thread
from .typecheck import type_check
from .varref import apply_format


@in_gdb_thread
def _compute_parameters(frame, stack_format):
    arg_iter = frame.frame_args()
    if arg_iter is None:
        return ""
    result = []
    for arg in arg_iter:
        desc = []
        name, val = symbol_value(arg, frame)
        if stack_format["parameterTypes"]:
            desc.append("[" + str(val.type) + "]")
        if stack_format["parameterNames"]:
            desc.append(name)
            if stack_format["parameterValues"]:
                desc.append("=")
        if stack_format["parameterValues"]:
            desc.append(val.format_string(summary=True))
        result.append(" ".join(desc))
    return ", ".join(result)


@in_gdb_thread
def _backtrace(thread_id, levels, startFrame, stack_format):
    with apply_format(stack_format):
        set_thread(thread_id)
        frames = []
        frame_iter = dap_frame_generator(startFrame, levels, stack_format["includeAll"])
        for frame_id, current_frame in frame_iter:
            pc = current_frame.address()
            name = current_frame.function()
            if stack_format["parameters"] and (
                stack_format["parameterTypes"]
                or stack_format["parameterNames"]
                or stack_format["parameterValues"]
            ):
                name += "(" + _compute_parameters(current_frame, stack_format) + ")"
            newframe = {
                "id": frame_id,
                "line": 0,
                "column": 0,
                "instructionPointerReference": hex(pc),
            }
            line = current_frame.line()
            if line is not None:
                newframe["line"] = export_line(line)
                if stack_format["line"]:
                    name += ", line " + str(line)
            objfile = gdb.current_progspace().objfile_for_address(pc)
            if objfile is not None:
                newframe["moduleId"] = module_id(objfile)
                if stack_format["module"]:
                    name += ", module " + objfile.username
            filename = current_frame.filename()
            if filename is not None:
                newframe["source"] = make_source(filename)
            newframe["name"] = name
            frames.append(newframe)
        return {
            "stackFrames": frames,
        }


@type_check
def check_stack_frame(
    *,
    hex: Optional[bool] = False,
    parameters: Optional[bool] = False,
    parameterTypes: Optional[bool] = False,
    parameterNames: Optional[bool] = False,
    parameterValues: Optional[bool] = False,
    line: Optional[bool] = False,
    module: Optional[bool] = False,
    includeAll: Optional[bool] = False,
    **rest
):
    return {
        "hex": hex,
        "parameters": parameters,
        "parameterTypes": parameterTypes,
        "parameterNames": parameterNames,
        "parameterValues": parameterValues,
        "line": line,
        "module": module,
        "includeAll": includeAll,
    }


@request("stackTrace")
@capability("supportsDelayedStackTraceLoading")
def stacktrace(
    *, levels: int = 0, startFrame: int = 0, threadId: int, format=None, **extra
):
    if format is None:
        format = {}
    format = check_stack_frame(**format)
    return _backtrace(threadId, levels, startFrame, format)
