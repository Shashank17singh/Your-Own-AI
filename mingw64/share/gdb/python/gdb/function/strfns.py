"""$_memeq, $_strlen, $_streq, $_regex"""

import re
import gdb


class _MemEq(gdb.Function):
    """$_memeq - compare bytes of memory.
    Usage: $_memeq (A, B, LEN)
    Returns:
      True if LEN bytes at A and B compare equally."""

    def __init__(self):
        super(_MemEq, self).__init__("_memeq")

    def invoke(self, a, b, length):
        if length < 0:
            raise ValueError("length must be non-negative")
        if length == 0:
            return True
        byte_vector = gdb.lookup_type("char").vector(length - 1)
        ptr_byte_vector = byte_vector.pointer()
        a_ptr = a.reinterpret_cast(ptr_byte_vector)
        b_ptr = b.reinterpret_cast(ptr_byte_vector)
        return a_ptr.dereference() == b_ptr.dereference()


class _StrLen(gdb.Function):
    """$_strlen - compute string length.
    Usage: $_strlen (A)
    Returns:
      Length of string A, assumed to be a string in the current language."""

    def __init__(self):
        super(_StrLen, self).__init__("_strlen")

    def invoke(self, a):
        s = a.string()
        return len(s)


class _StrEq(gdb.Function):
    """$_streq - check string equality.
    Usage: $_streq (A, B)
    Returns:
      True if A and B are identical strings in the current language.
    Example (amd64-linux):
      catch syscall open
      cond $bpnum $_streq((char*) $rdi, "foo")"""

    def __init__(self):
        super(_StrEq, self).__init__("_streq")

    def invoke(self, a, b):
        return a.string() == b.string()


class _RegEx(gdb.Function):
    """$_regex - check if a string matches a regular expression.
    Usage: $_regex (STRING, REGEX)
    Returns:
      True if string STRING (in the current language) matches the
      regular expression REGEX."""

    def __init__(self):
        super(_RegEx, self).__init__("_regex")

    def invoke(self, string, regex):
        s = string.string()
        r = re.compile(regex.string())
        return bool(r.match(s))


_MemEq()
_StrLen()
_StrEq()
_RegEx()
