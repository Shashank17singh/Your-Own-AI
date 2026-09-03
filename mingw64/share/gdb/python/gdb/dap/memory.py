import base64
import gdb
from .server import capability, request
from .startup import DAPException


@request("readMemory")
@capability("supportsReadMemoryRequest")
def read_memory(*, memoryReference: str, offset: int = 0, count: int, **extra):
    addr = int(memoryReference, 0) + offset
    try:
        buf = gdb.selected_inferior().read_memory(addr, count)
    except MemoryError as e:
        raise DAPException("Out of memory") from e
    return {
        "address": hex(addr),
        "data": base64.b64encode(buf).decode("ASCII"),
    }


@request("writeMemory")
@capability("supportsWriteMemoryRequest")
def write_memory(*, memoryReference: str, offset: int = 0, data: str, **extra):
    addr = int(memoryReference, 0) + offset
    buf = base64.b64decode(data)
    gdb.selected_inferior().write_memory(addr, buf)
