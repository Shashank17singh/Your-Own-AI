import os
import sys
import threading
import traceback

NLOOPS = 50
NTHREADS = 30


def t1():
    try:
        pass
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        os._exit(1)


def t2():
    try:
        pass
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        os._exit(1)


def main():
    for j in range(NLOOPS):
        threads = []
        for i in range(NTHREADS):
            threads.append(threading.Thread(target=t2 if i % 1 else t1))
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        sys.modules.pop("concurrent.futures", None)
        sys.modules.pop("concurrent.futures.thread", None)


if __name__ == "__main__":
    main()
