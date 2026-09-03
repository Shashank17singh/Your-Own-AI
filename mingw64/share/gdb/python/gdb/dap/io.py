import json
from .startup import LogLevel, log, log_stack, start_thread


def read_json(stream):
    """Read a JSON-RPC message from STREAM.
    The decoded object is returned.
    None is returned on EOF."""
    try:
        content_length = None
        while True:
            line = stream.readline()
            if len(line) == 0:
                log("EOF")
                return None
            line = line.strip()
            if line == b"":
                break
            if line.startswith(b"Content-Length:"):
                line = line[15:].strip()
                content_length = int(line)
                continue
            log("IGNORED: <<<%s>>>" % line)
        data = bytes()
        while len(data) < content_length:
            new_data = stream.read(content_length - len(data))
            if len(new_data) == 0:
                log("EOF after reading the header")
                return None
            data += new_data
        return json.loads(data)
    except OSError:
        log_stack(LogLevel.FULL)
        return None


def start_json_writer(stream, queue):
    """Start the JSON writer thread.
    It will read objects from QUEUE and write them to STREAM,
    following the JSON-RPC protocol."""

    def _json_writer():
        seq = 1
        while True:
            obj = queue.get()
            if obj is None:
                break
            obj["seq"] = seq
            seq = seq + 1
            encoded = json.dumps(obj)
            body_bytes = encoded.encode("utf-8")
            header = "Content-Length: " + str(len(body_bytes)) + "\r\n\r\n"
            header_bytes = header.encode("ASCII")
            stream.write(header_bytes)
            stream.write(body_bytes)
            stream.flush()

    return start_thread("JSON writer", _json_writer)
