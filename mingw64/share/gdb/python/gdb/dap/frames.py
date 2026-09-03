import itertools
from typing import Dict
import gdb
from gdb.frames import frame_iterator
from .startup import in_gdb_thread
from .state import set_thread

_all_frames = []
_iter_map = {}
thread_ids: Dict[int, int] = {}


@in_gdb_thread
def _clear_frame_ids(evt):
    global _all_frames
    _all_frames = []
    global _iter_map
    _iter_map = {}
    global thread_ids
    thread_ids = {}


gdb.events.cont.connect(_clear_frame_ids)


@in_gdb_thread
def frame_for_id(id):
    """Given a frame identifier ID, return the corresponding frame."""
    if id in thread_ids:
        thread_id = thread_ids[id]
        if thread_id != gdb.selected_thread().global_num:
            set_thread(thread_id)
    return _all_frames[id]


@in_gdb_thread
def select_frame(id):
    """Given a frame identifier ID, select the corresponding frame."""
    frame = frame_for_id(id)
    frame.inferior_frame().select()


class _MemoizingIterator:
    def __init__(self, iterator):
        self._iterator = iterator
        self._seen = []

    def __iter__(self):
        for item in self._seen:
            yield item
        for item in self._iterator:
            self._seen.append(item)
            yield item


@in_gdb_thread
def _frame_id_generator():
    try:
        base_iterator = frame_iterator(gdb.newest_frame(), 0, -1)
    except gdb.error:
        base_iterator = ()

    def get_id(frame):
        num = len(_all_frames)
        _all_frames.append(frame)
        thread_ids[num] = gdb.selected_thread().global_num
        return num

    def yield_frames(iterator, for_elided):
        for frame in iterator:
            yield (get_id(frame), for_elided, frame)
            elided = frame.elided()
            if elided is not None:
                yield from yield_frames(frame.elided(), True)

    yield from yield_frames(base_iterator, False)


@in_gdb_thread
def _get_frame_iterator():
    thread_id = gdb.selected_thread().global_num
    if thread_id not in _iter_map:
        _iter_map[thread_id] = _MemoizingIterator(_frame_id_generator())
    return _iter_map[thread_id]


@in_gdb_thread
def dap_frame_generator(frame_low, levels, include_all):
    """A generator that yields identifiers and frames.
    Each element is a pair of the form (ID, FRAME).
    ID is the internally-assigned frame ID.
    FRAME is a FrameDecorator of some kind.
    Arguments are as to the stackTrace request."""
    base_iterator = _get_frame_iterator()
    if not include_all:
        base_iterator = itertools.filterfalse(lambda item: item[1], base_iterator)
    if levels == 0:
        frame_high = None
    else:
        frame_high = frame_low + levels
    base_iterator = itertools.islice(base_iterator, frame_low, frame_high)
    for ident, _, frame in base_iterator:
        yield (ident, frame)
