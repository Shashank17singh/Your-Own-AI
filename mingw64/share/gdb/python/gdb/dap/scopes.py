import gdb
from .frames import frame_for_id
from .globalvars import get_global_scope
from .server import export_line, request
from .sources import make_source
from .startup import in_gdb_thread
from .varref import BaseReference

frame_to_scope = {}
_last_return_value = None


@in_gdb_thread
def clear_scopes(event):
    global frame_to_scope
    frame_to_scope = {}
    global _last_return_value
    _last_return_value = None


gdb.events.cont.connect(clear_scopes)


@in_gdb_thread
def set_finish_value(val):
    """Set the current 'finish' value on a stop."""
    global _last_return_value
    _last_return_value = val


@in_gdb_thread
def symbol_value(sym, frame):
    inf_frame = frame.inferior_frame()
    inf_frame.select()
    name = str(sym.symbol())
    val = sym.value()
    if val is None:
        val = sym.symbol().value(inf_frame)
    elif not isinstance(val, gdb.Value):
        val = gdb.Value(val)
    return (name, val)


class _ScopeReference(BaseReference):
    def __init__(self, name, hint, frameId: int, var_list):
        super().__init__(name)
        self._hint = hint
        self._frameId = frameId
        self._var_list = tuple(var_list)

    def to_object(self):
        result = super().to_object()
        result["presentationHint"] = self._hint
        result["expensive"] = False
        result["namedVariables"] = self.child_count()
        frame = frame_for_id(self._frameId)
        if frame.line() is not None:
            result["line"] = export_line(frame.line())
        filename = frame.filename()
        if filename is not None:
            result["source"] = make_source(filename)
        return result

    def has_children(self):
        return True

    def child_count(self):
        return len(self._var_list)

    @in_gdb_thread
    def fetch_one_child(self, idx):
        return symbol_value(self._var_list[idx], frame_for_id(self._frameId))


class _FinishScopeReference(_ScopeReference):
    def __init__(self, frameId):
        super().__init__("Return", "returnValue", frameId, ())

    def child_count(self):
        return 1

    def fetch_one_child(self, idx):
        assert idx == 0
        return ("(return)", _last_return_value)


class _RegisterReference(_ScopeReference):
    def __init__(self, name, frameId):
        super().__init__(
            name,
            "registers",
            frameId,
            frame_for_id(frameId).inferior_frame().architecture().registers(),
        )

    @in_gdb_thread
    def fetch_one_child(self, idx):
        return (
            self._var_list[idx].name,
            frame_for_id(self._frameId)
            .inferior_frame()
            .read_register(self._var_list[idx]),
        )


@request("scopes")
def scopes(*, frameId: int, **extra):
    if frameId in frame_to_scope:
        scopes = frame_to_scope[frameId]
    else:
        frame = frame_for_id(frameId)
        scopes = []
        args = tuple(frame.frame_args() or ())
        if args:
            scopes.append(_ScopeReference("Arguments", "arguments", frameId, args))
        has_return_value = frameId == 0 and _last_return_value is not None
        locs = tuple(frame.frame_locals() or ())
        if locs:
            scopes.append(_ScopeReference("Locals", "locals", frameId, locs))
        scopes.append(_RegisterReference("Registers", frameId))
        if has_return_value:
            scopes.append(_FinishScopeReference(frameId))
        frame_to_scope[frameId] = scopes
        global_scope = get_global_scope(frame)
        if global_scope is not None:
            scopes.append(global_scope)
    return {"scopes": [x.to_object() for x in scopes]}
