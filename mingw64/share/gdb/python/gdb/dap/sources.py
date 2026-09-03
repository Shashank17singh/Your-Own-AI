import os
from .server import capability, request
from .startup import DAPException, exec_mi_and_log, in_gdb_thread

_next_source = 1
_source_map = {}
_id_map = {}


@in_gdb_thread
def make_source(fullname, filename=None):
    """Return the Source for a given file name.
    FULLNAME is the full name.  This is used as the key.
    FILENAME is the base name; if None (the default), then it is
    computed from FULLNAME.
    """
    if fullname in _source_map:
        result = _source_map[fullname]
    else:
        if filename is None:
            filename = os.path.basename(fullname)
        result = {
            "name": filename,
            "path": fullname,
        }
        if not os.path.exists(fullname):
            global _next_source
            result["sourceReference"] = _next_source
            _id_map[_next_source] = result
            _next_source += 1
        _source_map[fullname] = result
    return result


@in_gdb_thread
def decode_source(source):
    """Decode a Source object.
    Finds and returns the filename of a given Source object."""
    if "sourceReference" not in source or source["sourceReference"] <= 0:
        if "path" in source:
            return source["path"]
        raise DAPException("either 'path' or 'sourceReference' must appear in Source")
    ref = source["sourceReference"]
    if ref not in _id_map:
        raise DAPException("no sourceReference " + str(ref))
    return _id_map[ref]["path"]


@request("loadedSources")
@capability("supportsLoadedSourcesRequest")
def loaded_sources(**extra):
    result = []
    for elt in exec_mi_and_log("-file-list-exec-source-files")["files"]:
        result.append(make_source(elt["fullname"], elt["file"]))
    return {
        "sources": result,
    }


@request("source")
def source(*, source=None, sourceReference: int, **extra):
    if source is None:
        source = {"sourceReference": sourceReference}
    filename = decode_source(source)
    with open(filename) as f:
        content = f.read()
    return {
        "content": content,
    }
