from typing import Optional
from .server import capability, export_line, import_line, request
from .sources import decode_source
from .startup import exec_mi_and_log


@request("breakpointLocations", expect_stopped=False)
@capability("supportsBreakpointLocationsRequest")
def breakpoint_locations(*, source, line: int, endLine: Optional[int] = None, **extra):
    line = import_line(line)
    if endLine is None:
        endLine = line
    else:
        endLine = import_line(endLine)
    filename = decode_source(source)
    lines = set()
    for entry in exec_mi_and_log("-symbol-list-lines", filename)["lines"]:
        this_line = entry["line"]
        if this_line >= line and this_line <= endLine:
            lines.add(export_line(this_line))
    return {"breakpoints": [{"line": x} for x in sorted(lines)]}
