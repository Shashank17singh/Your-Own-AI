import re
import gdb


class CallerIs(gdb.Function):
    """Check the calling function's name.
    Usage: $_caller_is (NAME [, NUMBER-OF-FRAMES])
    Arguments:
      NAME: The name of the function to search for.
      NUMBER-OF-FRAMES: How many stack frames to traverse back from the currently
        selected frame to compare with.  If the value is greater than the depth of
        the stack from that point then the result is False.
        The default is 1.
    Returns:
      True if the function's name at the specified frame is equal to NAME."""

    def __init__(self):
        super(CallerIs, self).__init__("_caller_is")

    def invoke(self, name, nframes=1):
        if nframes < 0:
            raise ValueError("nframes must be >= 0")
        frame = gdb.selected_frame()
        while nframes > 0:
            frame = frame.older()
            if frame is None:
                return False
            nframes = nframes - 1
        return frame.name() == name.string()


class CallerMatches(gdb.Function):
    """Compare the calling function's name with a regexp.
    Usage: $_caller_matches (REGEX [, NUMBER-OF-FRAMES])
    Arguments:
      REGEX: The regular expression to compare the function's name with.
      NUMBER-OF-FRAMES: How many stack frames to traverse back from the currently
        selected frame to compare with.  If the value is greater than the depth of
        the stack from that point then the result is False.
        The default is 1.
    Returns:
      True if the function's name at the specified frame matches REGEX."""

    def __init__(self):
        super(CallerMatches, self).__init__("_caller_matches")

    def invoke(self, name, nframes=1):
        if nframes < 0:
            raise ValueError("nframes must be >= 0")
        frame = gdb.selected_frame()
        while nframes > 0:
            frame = frame.older()
            if frame is None:
                return False
            nframes = nframes - 1
        return re.match(name.string(), frame.name()) is not None


class AnyCallerIs(gdb.Function):
    """Check all calling function's names.
    Usage: $_any_caller_is (NAME [, NUMBER-OF-FRAMES])
    Arguments:
      NAME: The name of the function to search for.
      NUMBER-OF-FRAMES: How many stack frames to traverse back from the currently
        selected frame to compare with.  If the value is greater than the depth of
        the stack from that point then the result is False.
        The default is 1.
    Returns:
      True if any function's name is equal to NAME."""

    def __init__(self):
        super(AnyCallerIs, self).__init__("_any_caller_is")

    def invoke(self, name, nframes=1):
        if nframes < 0:
            raise ValueError("nframes must be >= 0")
        frame = gdb.selected_frame()
        while nframes >= 0:
            if frame.name() == name.string():
                return True
            frame = frame.older()
            if frame is None:
                return False
            nframes = nframes - 1
        return False


class AnyCallerMatches(gdb.Function):
    """Compare all calling function's names with a regexp.
    Usage: $_any_caller_matches (REGEX [, NUMBER-OF-FRAMES])
    Arguments:
      REGEX: The regular expression to compare the function's name with.
      NUMBER-OF-FRAMES: How many stack frames to traverse back from the currently
        selected frame to compare with.  If the value is greater than the depth of
        the stack from that point then the result is False.
        The default is 1.
    Returns:
      True if any function's name matches REGEX."""

    def __init__(self):
        super(AnyCallerMatches, self).__init__("_any_caller_matches")

    def invoke(self, name, nframes=1):
        if nframes < 0:
            raise ValueError("nframes must be >= 0")
        frame = gdb.selected_frame()
        name_re = re.compile(name.string())
        while nframes >= 0:
            if name_re.match(frame.name()) is not None:
                return True
            frame = frame.older()
            if frame is None:
                return False
            nframes = nframes - 1
        return False


CallerIs()
CallerMatches()
AnyCallerIs()
AnyCallerMatches()
