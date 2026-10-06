"""Configure GDB using the WRS/Linux environment."""

import os

if "ENV_PREFIX" in os.environ:
    gdb.execute("set sysroot {}".format(os.environ["ENV_PREFIX"]))  # noqa: F821
else:
    print("warning: ENV_PREFIX environment variable missing.")
    print("The debugger will probably be unable to find the correct system libraries")
