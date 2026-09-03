"""Utilities for styling."""

import gdb

try:
    from pygments import formatters, highlight, lexers
    from pygments.filters import TokenMergeFilter
    from pygments.token import Comment, Error, Text
    from pygments.util import ClassNotFound

    _formatter = None

    def get_formatter():
        global _formatter
        if _formatter is None:
            _formatter = formatters.TerminalFormatter()
        return _formatter

    def colorize(filename, contents, lang):
        try:
            try:
                lexer = lexers.get_lexer_by_name(lang, stripnl=False)
            except ClassNotFound:
                lexer = lexers.get_lexer_for_filename(filename, stripnl=False)
            formatter = get_formatter()
            return highlight(contents, lexer, formatter).encode(
                gdb.host_charset(), "backslashreplace"
            )
        except Exception:
            return None

    class HandleNasmComments(TokenMergeFilter):
        @staticmethod
        def fix_comments(lexer, stream):
            in_comment = False
            for ttype, value in stream:
                if ttype is Error and value == "#":
                    in_comment = True
                if in_comment:
                    if ttype is Text and value == "\n":
                        in_comment = False
                    else:
                        ttype = Comment.Single
                yield ttype, value

        def filter(self, lexer, stream):
            f = HandleNasmComments.fix_comments
            return super().filter(lexer, f(lexer, stream))

    _asm_lexers = {}

    def __get_asm_lexer(gdbarch):
        lexer_type = "asm"
        try:
            flavor = gdb.parameter("disassembly-flavor")
            if flavor == "intel" and gdbarch.name()[:4] == "i386":
                lexer_type = "nasm"
        except Exception:
            pass
        if lexer_type not in _asm_lexers:
            _asm_lexers[lexer_type] = lexers.get_lexer_by_name(lexer_type)
            _asm_lexers[lexer_type].add_filter(HandleNasmComments())
            _asm_lexers[lexer_type].add_filter("raiseonerror")
        return _asm_lexers[lexer_type]

    def colorize_disasm(content, gdbarch):
        try:
            lexer = __get_asm_lexer(gdbarch)
            formatter = get_formatter()
            return highlight(content, lexer, formatter).rstrip().encode()
        except Exception:
            return content

except ImportError:

    def colorize(filename, contents, lang):
        return None

    def colorize_disasm(content, gdbarch):
        return None
