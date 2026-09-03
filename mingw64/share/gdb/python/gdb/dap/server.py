import functools
import heapq
import inspect
import json
import threading
from contextlib import contextmanager
import gdb
from .io import read_json, start_json_writer
from .startup import (
    DAPException,
    DAPQueue,
    LogLevel,
    exec_and_log,
    in_dap_thread,
    in_gdb_thread,
    log,
    log_stack,
    start_thread,
    thread_log,
)
from .typecheck import type_check

_capabilities = {}
_commands = {}
_server = None
_lines_start_at_1 = False
_columns_start_at_1 = False


class DeferredRequest:
    """If a DAP request function returns a deferred request, no
    response is sent immediately.
    Instead, request processing continues, with this particular
    request remaining un-replied-to.
    Later, when the result is available, the deferred request can be
    scheduled.  This causes 'invoke' to be called and then the
    response to be sent to the client.
    """

    def set_request(self, req, result):
        self._req = req
        self._result = result

    @in_dap_thread
    def defer_events(self):
        """Return True if events should be deferred during execution.
        This may be overridden by subclasses."""
        return True

    @in_dap_thread
    def invoke(self):
        """Implement the deferred request.
        This will be called from 'reschedule' (and should not be
        called elsewhere).  It should return the 'body' that will be
        sent in the response.  None means no 'body' field will be set.
        Subclasses must override this.
        """
        pass

    @in_dap_thread
    def reschedule(self):
        """Call this to reschedule this deferred request.
        This will call 'invoke' after the appropriate bookkeeping and
        will arrange for its result to be reported to the client.
        """
        with _server.canceller.current_request(self._req):
            if self.defer_events():
                _server.set_defer_events()
            _server.invoke_request(self._req, self._result, self.invoke)
        _server.emit_pending_events()


class NotStoppedException(Exception):
    pass


class CancellationHandler:
    def __init__(self):
        self.lock = threading.RLock()
        self.in_flight_dap_thread = None
        self.in_flight_gdb_thread = None
        self._reqs = []
        self._deferred_ids = set()

    @contextmanager
    def current_request(self, req):
        """Return a new context manager that registers that request
        REQ has started."""
        try:
            with self.lock:
                self.in_flight_dap_thread = req
            yield
        finally:
            with self.lock:
                self.in_flight_dap_thread = None

    def defer_request(self, req):
        """Indicate that the request REQ has been deferred."""
        with self.lock:
            self._deferred_ids.add(req)

    def request_finished(self, req):
        """Indicate that the request REQ is finished.
        It doesn't matter whether REQ succeeded or failed, only that
        processing for it is done.
        """
        with self.lock:
            self._deferred_ids.discard(req)

    def check_cancel(self, req):
        """Check whether request REQ is cancelled.
        If so, raise KeyboardInterrupt."""
        with self.lock:
            deferred = []
            try:
                while len(self._reqs) > 0 and self._reqs[0] <= req:
                    next_id = heapq.heappop(self._reqs)
                    if next_id == req:
                        raise KeyboardInterrupt()
                    elif next_id in self._deferred_ids:
                        deferred.append(next_id)
            finally:
                for x in deferred:
                    heapq.heappush(self._reqs, x)

    def cancel(self, req):
        """Call to cancel a request.
        If the request has already finished, this is ignored.
        If the request is in flight, it is interrupted.
        If the request has not yet been seen, the cancellation is queued."""
        with self.lock:
            if req == self.in_flight_gdb_thread:
                gdb.interrupt()
            else:
                heapq.heappush(self._reqs, req)

    @contextmanager
    def interruptable_region(self, req):
        """Return a new context manager that sets in_flight_gdb_thread to
        REQ."""
        if req is None:
            yield
            return
        try:
            with self.lock:
                self.check_cancel(req)
                self.in_flight_gdb_thread = req
            yield
        finally:
            with self.lock:
                self.in_flight_gdb_thread = None


class Server:
    """The DAP server class."""

    def __init__(self, in_stream, out_stream, child_stream):
        self._in_stream = in_stream
        self._out_stream = out_stream
        self._child_stream = child_stream
        self._delayed_fns_lock = threading.Lock()
        self._defer_events = False
        self._delayed_fns = []
        self._write_queue = DAPQueue()
        self._read_queue = DAPQueue()
        self._done = False
        self.canceller = CancellationHandler()
        global _server
        _server = self

    @in_dap_thread
    def invoke_request(self, req, result, fn):
        try:
            self.canceller.check_cancel(req)
            fn_result = fn()
            result["success"] = True
            if isinstance(fn_result, DeferredRequest):
                fn_result.set_request(req, result)
                self.canceller.defer_request(req)
                return
            elif fn_result is not None:
                result["body"] = fn_result
        except NotStoppedException:
            result["success"] = False
            result["message"] = "notStopped"
        except KeyboardInterrupt:
            result["success"] = False
            result["message"] = "cancelled"
        except DAPException as e:
            log_stack(LogLevel.FULL)
            result["success"] = False
            result["message"] = str(e)
        except BaseException as e:
            log_stack()
            result["success"] = False
            result["message"] = str(e)
        self.canceller.request_finished(req)
        self._send_json(result)

    @in_dap_thread
    def _handle_command(self, params):
        req = params["seq"]
        result = {
            "request_seq": req,
            "type": "response",
            "command": params["command"],
        }
        if "arguments" in params:
            args = params["arguments"]
        else:
            args = {}

        def fn():
            return _commands[params["command"]](**args)

        self.invoke_request(req, result, fn)

    def _read_inferior_output(self):
        while True:
            line = self._child_stream.readline()
            self.send_event_maybe_later(
                "output",
                {
                    "category": "stdout",
                    "output": line,
                },
            )

    def _send_json(self, obj):
        log("WROTE: <<<" + json.dumps(obj) + ">>>")
        self._write_queue.put(obj)

    def _reader_thread(self):
        while True:
            cmd = read_json(self._in_stream)
            if cmd is None:
                break
            log("READ: <<<" + json.dumps(cmd) + ">>>")
            if (
                "command" in cmd
                and cmd["command"] == "cancel"
                and "arguments" in cmd
                and "requestId" in cmd["arguments"]
            ):
                self.canceller.cancel(cmd["arguments"]["requestId"])
            self._read_queue.put(cmd)
        self._read_queue.put(None)

    @in_dap_thread
    def emit_pending_events(self):
        """Emit any pending events."""
        fns = None
        with self._delayed_fns_lock:
            fns = self._delayed_fns
            self._delayed_fns = []
            self._defer_events = False
        for fn in fns:
            fn()

    @in_dap_thread
    def main_loop(self):
        """The main loop of the DAP server."""
        start_thread("output reader", self._read_inferior_output)
        json_writer = start_json_writer(self._out_stream, self._write_queue)
        start_thread("JSON reader", self._reader_thread)
        while not self._done:
            cmd = self._read_queue.get()
            if cmd is None:
                break
            req = cmd["seq"]
            with self.canceller.current_request(req):
                self._handle_command(cmd)
            self.emit_pending_events()
        self._write_queue.put(None)
        json_writer.join()
        send_gdb("quit")

    @in_dap_thread
    def set_defer_events(self):
        """Defer any events until the current request has completed."""
        with self._delayed_fns_lock:
            self._defer_events = True

    def send_event_maybe_later(self, event, body=None):
        """Send a DAP event back to the client, but if a request is in-flight
        within the dap thread and that request is configured to delay the event,
        wait until the response has been sent until the event is sent back to
        the client."""
        with self.canceller.lock:
            if self.canceller.in_flight_dap_thread:
                with self._delayed_fns_lock:
                    if self._defer_events:
                        self._delayed_fns.append(lambda: self._send_event(event, body))
                        return
        self._send_event(event, body)

    @in_dap_thread
    def call_function_later(self, fn):
        """Call FN later -- after the current request's response has been sent."""
        with self._delayed_fns_lock:
            self._delayed_fns.append(fn)

    def _send_event(self, event, body=None):
        """Send an event to the DAP client.
        EVENT is the name of the event, a string.
        BODY is the body of the event, an arbitrary object."""
        obj = {
            "type": "event",
            "event": event,
        }
        if body is not None:
            obj["body"] = body
        self._send_json(obj)

    def shutdown(self):
        """Request that the server shut down."""
        self._done = True


def send_event(event, body=None):
    """Send an event to the DAP client.
    EVENT is the name of the event, a string.
    BODY is the body of the event, an arbitrary object."""
    _server.send_event_maybe_later(event, body)


def call_function_later(fn):
    """Call FN later -- after the current request's response has been sent."""
    _server.call_function_later(fn)


def _check_not_running(func):
    @functools.wraps(func)
    def check(*args, **kwargs):
        from .events import inferior_running

        if inferior_running:
            raise NotStoppedException()
        return func(*args, **kwargs)

    return check


def request(
    name: str,
    *,
    response: bool = True,
    on_dap_thread: bool = False,
    expect_stopped: bool = True,
    defer_events: bool = True
):
    """A decorator for DAP requests.
    This registers the function as the implementation of the DAP
    request NAME.  By default, the function is invoked in the gdb
    thread, and its result is returned as the 'body' of the DAP
    response.
    Some keyword arguments are provided as well:
    If RESPONSE is False, the result of the function will not be
    waited for and no 'body' will be in the response.
    If ON_DAP_THREAD is True, the function will be invoked in the DAP
    thread.  When ON_DAP_THREAD is True, RESPONSE may not be False.
    If EXPECT_STOPPED is True (the default), then the request will
    fail with the 'notStopped' reason if it is processed while the
    inferior is running.  When EXPECT_STOPPED is False, the request
    will proceed regardless of the inferior's state.
    If DEFER_EVENTS is True, then make sure any events sent during the
    request processing are not sent to the client until the response
    has been sent.
    """
    assert not on_dap_thread or response

    def wrap(func):
        code = func.__code__
        try:
            assert code.co_posonlyargcount == 0
        except AttributeError:
            pass
        assert code.co_argcount == 0
        assert code.co_flags & inspect.CO_VARKEYWORDS
        func = type_check(func)
        if on_dap_thread:
            check_cmd = in_dap_thread(func)
        else:
            func = in_gdb_thread(func)
            if response:

                def sync_call(**args):
                    return send_gdb_with_response(lambda: func(**args))

                check_cmd = sync_call
            else:

                def non_sync_call(**args):
                    return send_gdb(lambda: func(**args))

                check_cmd = non_sync_call
        if defer_events:

            def deferring(**args):
                _server.set_defer_events()
                return check_cmd(**args)

            cmd = deferring
        else:
            cmd = check_cmd
        if expect_stopped:
            cmd = _check_not_running(cmd)
        assert name not in _commands
        _commands[name] = cmd
        return cmd

    return wrap


def capability(name, value=True):
    """A decorator that indicates that the wrapper function implements
    the DAP capability NAME."""

    def wrap(func):
        assert name not in _capabilities
        _capabilities[name] = value
        return func

    return wrap


def client_bool_capability(name, default=False):
    """Return the value of a boolean client capability.
    If the capability was not specified, or did not have boolean type,
    DEFAULT is returned.  DEFAULT defaults to False."""
    if name in _server.config and isinstance(_server.config[name], bool):
        return _server.config[name]
    return default


@request("initialize", on_dap_thread=True)
def initialize(**args):
    _server.config = args
    _server.send_event_maybe_later("initialized")
    global _lines_start_at_1
    _lines_start_at_1 = client_bool_capability("linesStartAt1", True)
    global _columns_start_at_1
    _columns_start_at_1 = client_bool_capability("columnsStartAt1", True)
    return _capabilities.copy()


@request("terminate", expect_stopped=False)
@capability("supportsTerminateRequest")
def terminate(**args):
    exec_and_log("kill")


@request("disconnect", on_dap_thread=True, expect_stopped=False)
@capability("supportTerminateDebuggee")
def disconnect(*, terminateDebuggee: bool = False, **args):
    if terminateDebuggee:
        send_gdb_with_response("kill")
    _server.shutdown()


@request("cancel", on_dap_thread=True, expect_stopped=False)
@capability("supportsCancelRequest")
def cancel(**args):
    return None


class Invoker(object):
    """A simple class that can invoke a gdb command."""

    def __init__(self, cmd):
        self._cmd = cmd

    @in_gdb_thread
    def __call__(self):
        exec_and_log(self._cmd)


class Cancellable(object):
    def __init__(self, fn, result_q=None):
        self._fn = fn
        self._result_q = result_q
        with _server.canceller.lock:
            self.req = _server.canceller.in_flight_dap_thread

    @in_gdb_thread
    def __call__(self):
        try:
            with _server.canceller.interruptable_region(self.req):
                val = self._fn()
                if self._result_q is not None:
                    self._result_q.put(val)
        except (Exception, KeyboardInterrupt) as e:
            if self._result_q is not None:
                self._result_q.put(e)
            elif isinstance(e, KeyboardInterrupt):
                pass
            else:
                err_string = "%s, %s" % (e, type(e))
                thread_log("caught exception: " + err_string)
                log_stack()


def send_gdb(cmd):
    """Send CMD to the gdb thread.
    CMD can be either a function or a string.
    If it is a string, it is passed to gdb.execute."""
    if isinstance(cmd, str):
        cmd = Invoker(cmd)
    gdb.post_event(Cancellable(cmd))


def send_gdb_with_response(fn):
    """Send FN to the gdb thread and return its result.
    If FN is a string, it is passed to gdb.execute and None is
    returned as the result.
    If FN throws an exception, this function will throw the
    same exception in the calling thread.
    """
    if isinstance(fn, str):
        fn = Invoker(fn)
    result_q = DAPQueue()
    gdb.post_event(Cancellable(fn, result_q))
    val = result_q.get()
    if isinstance(val, (Exception, KeyboardInterrupt)):
        raise val
    return val


def export_line(line: int) -> int:
    """Rewrite LINE according to client capability.
    This applies the linesStartAt1 capability as needed,
    when sending a line number from gdb to the client."""
    if not _lines_start_at_1:
        line = line - 1
    return line


def import_line(line: int) -> int:
    """Rewrite LINE according to client capability.
    This applies the linesStartAt1 capability as needed,
    when the client sends a line number to gdb."""
    if not _lines_start_at_1:
        line = line + 1
    return line


def export_column(column: int) -> int:
    """Rewrite COLUMN according to client capability.
    This applies the columnsStartAt1 capability as needed,
    when sending a column number from gdb to the client."""
    return column if _columns_start_at_1 else column - 1


def import_column(column: int) -> int:
    """Rewrite COLUMN according to client capability.
    This applies the columnsStartAt1 capability as needed,
    when the client sends a column number to gdb."""
    return column if _columns_start_at_1 else column + 1
