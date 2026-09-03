class FrameIterator(object):
    """A gdb.Frame iterator.  Iterates over gdb.Frames or objects that
    conform to that interface."""

    def __init__(self, frame_obj):
        """Initialize a FrameIterator.
        Arguments:
            frame_obj the starting frame."""
        super(FrameIterator, self).__init__()
        self.frame = frame_obj

    def __iter__(self):
        return self

    def __next__(self):
        """next implementation.
        Returns:
            The next oldest frame."""
        result = self.frame
        if result is None:
            raise StopIteration
        self.frame = result.older()
        return result
