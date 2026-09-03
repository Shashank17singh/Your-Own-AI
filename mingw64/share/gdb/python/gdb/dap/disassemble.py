import gdb
from .server import capability, export_line, request
from .sources import make_source


class _BlockTracker:
    def __init__(self):
        self._labels = {}
        self._blocks = set()

    def add_block(self, block):
        while block is not None:
            if block.is_static or block.is_global or block in self._blocks:
                return
            self._blocks.add(block)
            if block.function is not None:
                self._labels[block.start] = block.function.name
            for sym in block:
                if sym.addr_class == gdb.SYMBOL_LOC_LABEL:
                    self._labels[int(sym.value())] = sym.name
            block = block.superblock

    def add_pc(self, pc, result):
        self.add_block(gdb.block_for_pc(pc))
        if pc in self._labels:
            result["symbol"] = self._labels[pc]
        sal = gdb.find_pc_line(pc)
        if sal.symtab is not None:
            if sal.line != 0:
                result["line"] = export_line(sal.line)
            if sal.symtab.filename is not None:
                result["location"] = make_source(sal.symtab.filename)


@request("disassemble")
@capability("supportsDisassembleRequest")
def disassemble(
    *,
    memoryReference: str,
    offset: int = 0,
    instructionOffset: int = 0,
    instructionCount: int,
    **extra
):
    pc = int(memoryReference, 0) + offset
    inf = gdb.selected_inferior()
    try:
        arch = gdb.selected_frame().architecture()
    except gdb.error:
        arch = inf.architecture()
    tracker = _BlockTracker()
    result = []
    total_count = instructionOffset + instructionCount
    for elt in arch.disassemble(pc, count=total_count)[instructionOffset:]:
        mem = inf.read_memory(elt["addr"], elt["length"])
        insn = {
            "address": hex(elt["addr"]),
            "instruction": elt["asm"],
            "instructionBytes": mem.hex(),
        }
        tracker.add_pc(elt["addr"], insn)
        result.append(insn)
    return {
        "instructions": result,
    }
