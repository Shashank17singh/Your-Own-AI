"""Utilities for working with ptwrite filters."""

import gdb

_ptwrite_filter = {}
_ptwrite_filter_factory = None


def _ptwrite_exit_handler(event):
    """Exit handler to prune _ptwrite_filter on thread exit."""
    _ptwrite_filter.pop(event.inferior_thread.ptid, None)


gdb.events.thread_exited.connect(_ptwrite_exit_handler)


def _clear_traces():
    """Helper function to clear the trace of all threads."""
    current_thread = gdb.selected_thread()
    for inferior in gdb.inferiors():
        for thread in inferior.threads():
            thread.switch()
            recording = gdb.current_recording()
            if recording is not None:
                recording.clear()
    current_thread.switch()


def register_filter_factory(filter_factory_):
    """Register the ptwrite filter factory."""
    if filter_factory_ is not None and not callable(filter_factory_):
        raise TypeError("The filter factory must be callable or 'None'.")
    _clear_traces()
    _ptwrite_filter.clear()
    global _ptwrite_filter_factory
    _ptwrite_filter_factory = filter_factory_


def get_filter():
    """Returns the filter of the current thread."""
    thread = gdb.selected_thread()
    key = thread.ptid
    if key not in _ptwrite_filter:
        if _ptwrite_filter_factory is not None:
            _ptwrite_filter[key] = _ptwrite_filter_factory(thread)
        else:
            return None
    return _ptwrite_filter[key]
