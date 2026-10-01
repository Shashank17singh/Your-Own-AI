# Copyright 2009 Brian Quinlan. All Rights Reserved.
# Licensed to PSF under a Contributor Agreement.

"""Execute computations asynchronously using threads or processes."""

__author__ = "Brian Quinlan (brian@sweetapp.com)"

from concurrent.futures._base import (
    ALL_COMPLETED,
    FIRST_COMPLETED,
    FIRST_EXCEPTION,
    BrokenExecutor,
    CancelledError,
    Executor,
    Future,
    InvalidStateError,
    TimeoutError,
    as_completed,
    wait,
)

__all__ = (
    "ALL_COMPLETED",
    "FIRST_COMPLETED",
    "FIRST_EXCEPTION",
    "BrokenExecutor",
    "CancelledError",
    "Executor",
    "Future",
    "ProcessPoolExecutor",
    "ThreadPoolExecutor",
    "TimeoutError",
    "as_completed",
    "wait",
)


def __dir__():
    return __all__ + ("__author__", "__doc__")


def __getattr__(name):
    global ProcessPoolExecutor, ThreadPoolExecutor

    if name == "ProcessPoolExecutor":
        from .process import ProcessPoolExecutor as pe

        ProcessPoolExecutor = pe
        return pe

    if name == "ThreadPoolExecutor":
        from .thread import ThreadPoolExecutor as te

        ThreadPoolExecutor = te
        return te

    raise AttributeError(f"module {__name__} has no attribute {name}")
