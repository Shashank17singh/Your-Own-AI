import gdb
from .sources import make_source
from .startup import in_gdb_thread
from .varref import BaseReference

_id_to_scope = {}


@in_gdb_thread
def clear(event):
    global _id_to_scope
    _id_to_scope = {}


gdb.events.cont.connect(clear)


class _Globals(BaseReference):
    def __init__(self, filename, var_list):
        super().__init__("Globals")
        self._filename = filename
        self._var_list = var_list

    def to_object(self):
        result = super().to_object()
        result["presentationHint"] = "globals"
        result["expensive"] = False
        result["namedVariables"] = self.child_count()
        if self._filename is not None:
            result["source"] = make_source(self._filename)
        return result

    def has_children(self):
        return True

    def child_count(self):
        return len(self._var_list)

    @in_gdb_thread
    def fetch_one_child(self, idx):
        sym = self._var_list[idx]
        return (sym.name, sym.value())


@in_gdb_thread
def get_global_scope(frame):
    """Given a frame decorator, return the corresponding global scope
    object.
    If the frame does not have a block, or if the CU does not have
    globals (that is, empty static and global blocks), return None."""
    inf_frame = frame.inferior_frame()
    try:
        block = inf_frame.block()
    except RuntimeError:
        return None
    block = block.static_block
    if block in _id_to_scope:
        return _id_to_scope[block]
    syms = []
    block_iter = block
    while block_iter is not None:
        syms += [sym for sym in block_iter if sym.is_variable and not sym.is_artificial]
        block_iter = block_iter.superblock
    if len(syms) == 0:
        return None
    result = _Globals(frame.filename(), syms)
    _id_to_scope[block] = result
    return result
