"""GDB commands for working with pretty-printers."""

import copy
import re
import gdb


def parse_printer_regexps(arg):
    """Internal utility to parse a pretty-printer command argv.
    Arguments:
        arg: The arguments to the command.  The format is:
             [object-regexp [name-regexp]].
             Individual printers in a collection are named as
             printer-name;subprinter-name.
    Returns:
        The result is a 3-tuple of compiled regular expressions, except that
        the resulting compiled subprinter regexp is None if not provided.
    Raises:
        SyntaxError: an error processing ARG
    """
    argv = gdb.string_to_argv(arg)
    argc = len(argv)
    object_regexp = ""  # match everything
    name_regexp = ""  # match everything
    subname_regexp = None
    if argc > 3:
        raise SyntaxError("too many arguments")
    if argc >= 1:
        object_regexp = argv[0]
    if argc >= 2:
        name_subname = argv[1].split(";", 1)
        name_regexp = name_subname[0]
        if len(name_subname) == 2:
            subname_regexp = name_subname[1]
    try:
        object_re = re.compile(object_regexp)
    except SyntaxError:
        raise SyntaxError("invalid object regexp: %s" % object_regexp)
    try:
        name_re = re.compile(name_regexp)
    except SyntaxError:
        raise SyntaxError("invalid name regexp: %s" % name_regexp)
    if subname_regexp is not None:
        try:
            subname_re = re.compile(subname_regexp)
        except SyntaxError:
            raise SyntaxError("invalid subname regexp: %s" % subname_regexp)
    else:
        subname_re = None
    return (object_re, name_re, subname_re)


def printer_enabled_p(printer):
    """Internal utility to see if printer (or subprinter) is enabled."""
    if hasattr(printer, "enabled"):
        return printer.enabled
    else:
        return True


class InfoPrettyPrinter(gdb.Command):
    """GDB command to list all registered pretty-printers.
    Usage: info pretty-printer [OBJECT-REGEXP [NAME-REGEXP]]
    OBJECT-REGEXP is a regular expression matching the objects to list.
    Objects are "global", the program space's file, and the objfiles within
    that program space.
    NAME-REGEXP matches the name of the pretty-printer.
    Individual printers in a collection are named as
    printer-name;subprinter-name."""

    def __init__(self):
        super(InfoPrettyPrinter, self).__init__("info pretty-printer", gdb.COMMAND_DATA)

    @staticmethod
    def enabled_string(printer):
        """Return "" if PRINTER is enabled, otherwise " [disabled]"."""
        if printer_enabled_p(printer):
            return ""
        else:
            return " [disabled]"

    @staticmethod
    def printer_name(printer):
        """Return the printer's name."""
        if hasattr(printer, "name"):
            return printer.name
        if hasattr(printer, "__name__"):
            return printer.__name__
        return "unknown"

    def list_pretty_printers(self, pretty_printers, name_re, subname_re):
        """Print a list of pretty-printers."""
        sorted_pretty_printers = sorted(
            copy.copy(pretty_printers), key=self.printer_name
        )
        for printer in sorted_pretty_printers:
            name = self.printer_name(printer)
            enabled = self.enabled_string(printer)
            if name_re.match(name):
                print("  %s%s" % (name, enabled))
                if hasattr(printer, "subprinters") and printer.subprinters is not None:
                    sorted_subprinters = sorted(
                        copy.copy(printer.subprinters), key=self.printer_name
                    )
                    for subprinter in sorted_subprinters:
                        if not subname_re or subname_re.match(subprinter.name):
                            print(
                                "    %s%s"
                                % (subprinter.name, self.enabled_string(subprinter))
                            )

    def invoke1(
        self, title, printer_list, obj_name_to_match, object_re, name_re, subname_re
    ):
        """Subroutine of invoke to simplify it."""
        if printer_list and object_re.match(obj_name_to_match):
            print(title)
            self.list_pretty_printers(printer_list, name_re, subname_re)

    def invoke(self, arg, from_tty):
        """GDB calls this to perform the command."""
        object_re, name_re, subname_re = parse_printer_regexps(arg)
        self.invoke1(
            "global pretty-printers:",
            gdb.pretty_printers,
            "global",
            object_re,
            name_re,
            subname_re,
        )
        cp = gdb.current_progspace()
        self.invoke1(
            "progspace %s pretty-printers:" % cp.filename,
            cp.pretty_printers,
            "progspace",
            object_re,
            name_re,
            subname_re,
        )
        for objfile in gdb.objfiles():
            self.invoke1(
                "objfile %s pretty-printers:" % objfile.filename,
                objfile.pretty_printers,
                objfile.filename,
                object_re,
                name_re,
                subname_re,
            )


def count_enabled_printers(pretty_printers):
    """Return a 2-tuple of number of enabled and total printers."""
    enabled = 0
    total = 0
    for printer in pretty_printers:
        if hasattr(printer, "subprinters") and printer.subprinters is not None:
            if printer_enabled_p(printer):
                for subprinter in printer.subprinters:
                    if printer_enabled_p(subprinter):
                        enabled += 1
            total += len(printer.subprinters)
        else:
            if printer_enabled_p(printer):
                enabled += 1
            total += 1
    return (enabled, total)


def count_all_enabled_printers():
    """Return a 2-tuble of the enabled state and total number of all printers.
    This includes subprinters.
    """
    enabled_count = 0
    total_count = 0
    t_enabled, t_total = count_enabled_printers(gdb.pretty_printers)
    enabled_count += t_enabled
    total_count += t_total
    t_enabled, t_total = count_enabled_printers(gdb.current_progspace().pretty_printers)
    enabled_count += t_enabled
    total_count += t_total
    for objfile in gdb.objfiles():
        t_enabled, t_total = count_enabled_printers(objfile.pretty_printers)
        enabled_count += t_enabled
        total_count += t_total
    return (enabled_count, total_count)


def pluralize(text, n, suffix="s"):
    """Return TEXT pluralized if N != 1."""
    if n != 1:
        return "%s%s" % (text, suffix)
    else:
        return text


def show_pretty_printer_enabled_summary():
    """Print the number of printers enabled/disabled.
    We count subprinters individually.
    """
    enabled_count, total_count = count_all_enabled_printers()
    print("%d of %d printers enabled" % (enabled_count, total_count))


def do_enable_pretty_printer_1(pretty_printers, name_re, subname_re, flag):
    """Worker for enabling/disabling pretty-printers.
    Arguments:
        pretty_printers: list of pretty-printers
        name_re: regular-expression object to select printers
        subname_re: regular expression object to select subprinters or None
                    if all are affected
        flag: True for Enable, False for Disable
    Returns:
        The number of printers affected.
        This is just for informational purposes for the user.
    """
    total = 0
    for printer in pretty_printers:
        if (
            hasattr(printer, "name")
            and name_re.match(printer.name)
            or hasattr(printer, "__name__")
            and name_re.match(printer.__name__)
        ):
            if hasattr(printer, "subprinters") and printer.subprinters is not None:
                if not subname_re:
                    if printer_enabled_p(printer) != flag:
                        for subprinter in printer.subprinters:
                            if printer_enabled_p(subprinter):
                                total += 1
                    printer.enabled = flag
                else:
                    for subprinter in printer.subprinters:
                        if subname_re.match(subprinter.name):
                            if (
                                printer_enabled_p(printer)
                                and printer_enabled_p(subprinter) != flag
                            ):
                                total += 1
                            subprinter.enabled = flag
            else:
                if not subname_re:
                    if printer_enabled_p(printer) != flag:
                        total += 1
                    printer.enabled = flag
    return total


def do_enable_pretty_printer(arg, flag):
    """Internal worker for enabling/disabling pretty-printers."""
    object_re, name_re, subname_re = parse_printer_regexps(arg)
    total = 0
    if object_re.match("global"):
        total += do_enable_pretty_printer_1(
            gdb.pretty_printers, name_re, subname_re, flag
        )
    cp = gdb.current_progspace()
    if object_re.match("progspace"):
        total += do_enable_pretty_printer_1(
            cp.pretty_printers, name_re, subname_re, flag
        )
    for objfile in gdb.objfiles():
        if object_re.match(objfile.filename):
            total += do_enable_pretty_printer_1(
                objfile.pretty_printers, name_re, subname_re, flag
            )
    if flag:
        state = "enabled"
    else:
        state = "disabled"
    print("%d %s %s" % (total, pluralize("printer", total), state))
    show_pretty_printer_enabled_summary()


class EnablePrettyPrinter(gdb.Command):
    """GDB command to enable the specified pretty-printer.
    Usage: enable pretty-printer [OBJECT-REGEXP [NAME-REGEXP]]
    OBJECT-REGEXP is a regular expression matching the objects to examine.
    Objects are "global", the program space's file, and the objfiles within
    that program space.
    NAME-REGEXP matches the name of the pretty-printer.
    Individual printers in a collection are named as
    printer-name;subprinter-name."""

    def __init__(self):
        super(EnablePrettyPrinter, self).__init__(
            "enable pretty-printer", gdb.COMMAND_DATA
        )

    def invoke(self, arg, from_tty):
        """GDB calls this to perform the command."""
        do_enable_pretty_printer(arg, True)


class DisablePrettyPrinter(gdb.Command):
    """GDB command to disable the specified pretty-printer.
    Usage: disable pretty-printer [OBJECT-REGEXP [NAME-REGEXP]]
    OBJECT-REGEXP is a regular expression matching the objects to examine.
    Objects are "global", the program space's file, and the objfiles within
    that program space.
    NAME-REGEXP matches the name of the pretty-printer.
    Individual printers in a collection are named as
    printer-name;subprinter-name."""

    def __init__(self):
        super(DisablePrettyPrinter, self).__init__(
            "disable pretty-printer", gdb.COMMAND_DATA
        )

    def invoke(self, arg, from_tty):
        """GDB calls this to perform the command."""
        do_enable_pretty_printer(arg, False)


def register_pretty_printer_commands():
    """Call from a top level script to install the pretty-printer commands."""
    InfoPrettyPrinter()
    EnablePrettyPrinter()
    DisablePrettyPrinter()


register_pretty_printer_commands()
