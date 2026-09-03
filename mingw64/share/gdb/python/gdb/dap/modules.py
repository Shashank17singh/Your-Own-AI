import gdb
from .server import capability, request
from .startup import in_gdb_thread


@in_gdb_thread
def module_id(objfile):
    """Return the module ID for the objfile."""
    return objfile.username


@in_gdb_thread
def is_module(objfile):
    """Return True if OBJFILE represents a valid Module."""
    return objfile.is_valid() and objfile.owner is None


@in_gdb_thread
def make_module(objf):
    """Return a Module representing the objfile OBJF.
    The objfile must pass the 'is_module' test."""
    result = {
        "id": module_id(objf),
        "name": objf.username,
    }
    if objf.is_file:
        result["path"] = objf.filename
    return result


@capability("supportsModulesRequest")
@request("modules")
def modules(*, startModule: int = 0, moduleCount: int = 0, **args):
    objfiles = [x for x in gdb.objfiles() if is_module(x)]
    if moduleCount == 0:
        last = len(objfiles)
    else:
        last = startModule + moduleCount
    return {
        "modules": [make_module(x) for x in objfiles[startModule:last]],
        "totalModules": len(objfiles),
    }
