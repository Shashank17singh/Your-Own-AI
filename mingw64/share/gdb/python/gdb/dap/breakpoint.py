import re
from contextlib import contextmanager
from typing import Optional, Sequence
import gdb
from .server import capability, export_line, import_line, request, send_event
from .sources import make_source
from .startup import (
    DAPException,
    LogLevel,
    exec_mi_and_log,
    in_gdb_thread,
    log_stack,
    parse_and_eval,
)
from .typecheck import type_check

_suppress_bp = False


@contextmanager
def suppress_new_breakpoint_event():
    """Return a new context manager that suppresses new breakpoint events."""
    global _suppress_bp
    saved = _suppress_bp
    _suppress_bp = True
    try:
        yield None
    finally:
        _suppress_bp = saved


@in_gdb_thread
def _bp_modified(event):
    if not _suppress_bp:
        send_event(
            "breakpoint",
            {
                "reason": "changed",
                "breakpoint": _breakpoint_descriptor(event),
            },
        )


@in_gdb_thread
def _bp_created(event):
    if not _suppress_bp:
        send_event(
            "breakpoint",
            {
                "reason": "new",
                "breakpoint": _breakpoint_descriptor(event),
            },
        )


@in_gdb_thread
def _bp_deleted(event):
    if not _suppress_bp:
        send_event(
            "breakpoint",
            {
                "reason": "removed",
                "breakpoint": _breakpoint_descriptor(event),
            },
        )


gdb.events.breakpoint_created.connect(_bp_created)
gdb.events.breakpoint_modified.connect(_bp_modified)
gdb.events.breakpoint_deleted.connect(_bp_deleted)
breakpoint_map = {}


@in_gdb_thread
def _breakpoint_descriptor(bp):
    "Return the Breakpoint object descriptor given a gdb Breakpoint."
    pending = bp.pending or len(gdb.objfiles()) == 0
    result = {
        "id": bp.number,
        "verified": not pending,
    }
    if pending:
        result["reason"] = "pending"
    if bp.locations:
        loc = bp.locations[0]
        if loc.source:
            filename, line = loc.source
            if loc.fullname is not None:
                filename = loc.fullname
            result.update(
                {
                    "source": make_source(filename),
                    "line": export_line(line),
                }
            )
        if loc.address:
            result["instructionReference"] = hex(loc.address)
    return result


def _remove_entries(table, *names):
    return [table.pop(name, None) for name in names]


@in_gdb_thread
def _set_breakpoints_callback(kind, specs, creator):
    if kind in breakpoint_map:
        saved_map = breakpoint_map[kind]
    else:
        saved_map = {}
    breakpoint_map[kind] = {}
    result = []
    with suppress_new_breakpoint_event():
        for spec in specs:
            condition, hit_condition = _remove_entries(
                spec, "condition", "hitCondition"
            )
            keyspec = frozenset(spec.items())
            bp = None
            try:
                if keyspec in saved_map:
                    bp = saved_map.pop(keyspec)
                else:
                    bp = creator(**spec)
                bp.condition = condition
                if hit_condition is None:
                    bp.ignore_count = 0
                else:
                    bp.ignore_count = int(
                        parse_and_eval(hit_condition, global_context=True)
                    )
                breakpoint_map[kind][keyspec] = bp
                result.append(_breakpoint_descriptor(bp))
            except Exception as e:
                log_stack(LogLevel.FULL)
                if bp is not None:
                    bp.delete()
                result.append(
                    {
                        "verified": False,
                        "reason": "failed",
                        "message": str(e),
                    }
                )
        for entry in saved_map.values():
            entry.delete()
    return result


class _PrintBreakpoint(gdb.Breakpoint):
    def __init__(self, logMessage, **args):
        super().__init__(**args)
        self._message = re.split("{(.*?)}", logMessage)

    def stop(self):
        output = ""
        for idx, item in enumerate(self._message):
            if idx % 2 == 0:
                output += item
            else:
                try:
                    val = gdb.parse_and_eval(item)
                    output += str(val)
                except Exception as e:
                    output += "<" + str(e) + ">"
        send_event(
            "output",
            {
                "category": "console",
                "output": output,
            },
        )
        return False


@in_gdb_thread
def _set_one_breakpoint(*, logMessage=None, **args):
    if logMessage is not None:
        return _PrintBreakpoint(logMessage, **args)
    else:
        return gdb.Breakpoint(**args)


@in_gdb_thread
def _set_breakpoints(kind, specs):
    return _set_breakpoints_callback(kind, specs, _set_one_breakpoint)


@type_check
def _rewrite_src_breakpoint(
    *,
    source,
    line: int,
    condition: Optional[str] = None,
    hitCondition: Optional[str] = None,
    logMessage: Optional[str] = None,
    **args,
):
    return {
        "source": source["path"],
        "line": import_line(line),
        "condition": condition,
        "hitCondition": hitCondition,
        "logMessage": logMessage,
    }


@request("setBreakpoints", expect_stopped=False)
@capability("supportsHitConditionalBreakpoints")
@capability("supportsConditionalBreakpoints")
@capability("supportsLogPoints")
def set_breakpoint(*, source, breakpoints: Sequence = (), **args):
    if "path" not in source:
        result = []
    else:
        specs = []
        for bp in breakpoints:
            bp["source"] = source
            specs.append(_rewrite_src_breakpoint(**bp))
        key = "source:" + source["path"]
        result = _set_breakpoints(key, specs)
    return {
        "breakpoints": result,
    }


@type_check
def _rewrite_fn_breakpoint(
    *,
    name: str,
    condition: Optional[str] = None,
    hitCondition: Optional[str] = None,
    **args,
):
    return {
        "function": name,
        "condition": condition,
        "hitCondition": hitCondition,
    }


@request("setFunctionBreakpoints", expect_stopped=False)
@capability("supportsFunctionBreakpoints")
def set_fn_breakpoint(*, breakpoints: Sequence, **args):
    specs = [_rewrite_fn_breakpoint(**bp) for bp in breakpoints]
    return {
        "breakpoints": _set_breakpoints("function", specs),
    }


@type_check
def _rewrite_insn_breakpoint(
    *,
    instructionReference: str,
    offset: Optional[int] = None,
    condition: Optional[str] = None,
    hitCondition: Optional[str] = None,
    **args,
):
    val = "*" + instructionReference
    if offset is not None:
        val = val + " + " + str(offset)
    return {
        "spec": val,
        "condition": condition,
        "hitCondition": hitCondition,
    }


@request("setInstructionBreakpoints", expect_stopped=False)
@capability("supportsInstructionBreakpoints")
def set_insn_breakpoints(
    *, breakpoints: Sequence, offset: Optional[int] = None, **args
):
    specs = [_rewrite_insn_breakpoint(**bp) for bp in breakpoints]
    return {
        "breakpoints": _set_breakpoints("instruction", specs),
    }


@in_gdb_thread
def _catch_exception(filterId, **args):
    if filterId in ("assert", "exception", "throw", "rethrow", "catch"):
        cmd = "-catch-" + filterId
    else:
        raise DAPException("Invalid exception filterID: " + str(filterId))
    result = exec_mi_and_log(cmd)
    num = result["bkpt"]["number"]
    for bp in gdb.breakpoints():
        if bp.number == num:
            return bp
    raise Exception("Could not find catchpoint after creating")


@in_gdb_thread
def _set_exception_catchpoints(filter_options):
    return _set_breakpoints_callback("exception", filter_options, _catch_exception)


@type_check
def _rewrite_exception_breakpoint(
    *,
    filterId: str,
    condition: Optional[str] = None,
    **args,
):
    return {
        "filterId": filterId,
        "condition": condition,
    }


@request("setExceptionBreakpoints", expect_stopped=False)
@capability("supportsExceptionFilterOptions")
@capability(
    "exceptionBreakpointFilters",
    (
        {
            "filter": "assert",
            "label": "Ada assertions",
            "supportsCondition": True,
        },
        {
            "filter": "exception",
            "label": "Ada exceptions",
            "supportsCondition": True,
        },
        {
            "filter": "throw",
            "label": "C++ exceptions, when thrown",
            "supportsCondition": True,
        },
        {
            "filter": "rethrow",
            "label": "C++ exceptions, when re-thrown",
            "supportsCondition": True,
        },
        {
            "filter": "catch",
            "label": "C++ exceptions, when caught",
            "supportsCondition": True,
        },
    ),
)
def set_exception_breakpoints(
    *, filters: Sequence[str], filterOptions: Sequence = (), **args
):
    options = [{"filterId": filter} for filter in filters]
    options.extend(filterOptions)
    options = [_rewrite_exception_breakpoint(**bp) for bp in options]
    return {
        "breakpoints": _set_exception_catchpoints(options),
    }
