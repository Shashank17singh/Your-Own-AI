#
# Support for the API of the multiprocessing package using threads
#
# multiprocessing/dummy/__init__.py
#
# Copyright (c) 2006-2008, R Oudkerk
# Licensed to PSF under a Contributor Agreement.
#

__all__ = [
    "Barrier",
    "BoundedSemaphore",
    "Condition",
    "Event",
    "JoinableQueue",
    "Lock",
    "Manager",
    "Pipe",
    "Pool",
    "Process",
    "Queue",
    "RLock",
    "Semaphore",
    "active_children",
    "current_process",
    "freeze_support",
]

#
# Imports
#

import array
import sys
import threading
import weakref
from queue import Queue
from threading import (
    Barrier,
    BoundedSemaphore,
    Condition,
    Event,
    Lock,
    RLock,
    Semaphore,
)

from .connection import Pipe


class DummyProcess(threading.Thread):
    def __init__(self, group=None, target=None, name=None, args=(), kwargs=None):
        if kwargs is None:
            kwargs = {}
        threading.Thread.__init__(self, group, target, name, args, kwargs)
        self._pid = None
        self._children = weakref.WeakKeyDictionary()
        self._start_called = False
        self._parent = current_process()

    def start(self):
        if self._parent is not current_process():
            raise RuntimeError(
                f"Parent is {self._parent!r} but current_process is {current_process()!r}"
            )
        self._start_called = True
        if hasattr(self._parent, "_children"):
            self._parent._children[self] = None
        threading.Thread.start(self)

    @property
    def exitcode(self):
        if self._start_called and not self.is_alive():
            return 0
        else:
            return None


Process = DummyProcess
current_process = threading.current_thread
current_process()._children = weakref.WeakKeyDictionary()


def active_children():
    children = current_process()._children
    for p in list(children):
        if not p.is_alive():
            children.pop(p, None)
    return list(children)


def freeze_support():
    pass


class Namespace:
    def __init__(self, /, **kwds):
        self.__dict__.update(kwds)

    def __repr__(self):
        items = list(self.__dict__.items())
        temp = []
        for name, value in items:
            if not name.startswith("_"):
                temp.append(f"{name}={value!r}")
        temp.sort()
        return "{}({})".format(self.__class__.__name__, ", ".join(temp))


dict = dict  # noqa: PLW0127
list = list  # noqa: PLW0127


def Array(typecode, sequence, lock=True):
    return array.array(typecode, sequence)


class Value:
    def __init__(self, typecode, value, lock=True):
        self._typecode = typecode
        self._value = value

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        self._value = value

    def __repr__(self):
        return f"<{type(self).__name__}({self._typecode!r}, {self._value!r})>"


def Manager():
    return sys.modules[__name__]


def shutdown():
    pass


def Pool(processes=None, initializer=None, initargs=()):
    from ..pool import ThreadPool

    return ThreadPool(processes, initializer, initargs)


JoinableQueue = Queue
