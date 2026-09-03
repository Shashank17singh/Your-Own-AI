from typing import Optional
from .frames import select_frame
from .server import capability, import_column, import_line, request
from .startup import exec_mi_and_log


@request("completions")
@capability("supportsCompletionsRequest")
@capability("completionTriggerCharacters", [" ", "."])
def completions(
    *,
    frameId: Optional[int] = None,
    text: str,
    column: int,
    line: Optional[int] = None,
    **extra,
):
    if frameId is not None:
        select_frame(frameId)
    column = import_column(column)
    if line is None:
        line = 1
    else:
        line = import_line(line)
    if text:
        text = text.splitlines()[line - 1]
        text = text[: column - 1]
    else:
        text = ""
    mi_result = exec_mi_and_log("-complete", text)
    result = []
    completion = None
    if "completion" in mi_result:
        completion = mi_result["completion"]
        result.append({"label": completion, "length": len(completion)})
    if (
        completion is not None
        and len(mi_result["matches"]) == 1
        and completion == mi_result["matches"][0]
    ):
        return {"targets": result}
    for match in mi_result["matches"]:
        result.append({"label": match, "length": len(match)})
    return {"targets": result}
