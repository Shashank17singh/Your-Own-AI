from __future__ import print_function
import cppcheckdata
import sys
import re

Y2038_SAFE_TIME_BITS = 64
Y2038_SAFE_FILE_OFFSET_BITS = 64
re_define_time_bits_64 = re.compile(
    rf"^\s*#\s*define\s+_TIME_BITS\s+{Y2038_SAFE_TIME_BITS}\s*$"
)
re_define_time_bits = re.compile(r"^\s*#\s*define\s+_TIME_BITS\s+.*$")
re_undef_time_bits = re.compile(r"^\s*#\s*undef\s+_TIME_BITS\s*$")
re_define_use_time_bits64 = re.compile(r"^\s*#\s*define\s+_USE_TIME_BITS64\s*$")
re_undef_use_time_bits64 = re.compile(r"^\s*#\s*undef\s+_USE_TIME_BITS64\s*$")
re_define_file_offset_bits_64 = re.compile(
    rf"^\s*#\s*define\s+_FILE_OFFSET_BITS\s+{Y2038_SAFE_FILE_OFFSET_BITS}\s*$"
)
re_define_file_offset_bits = re.compile(r"^\s*#\s*define\s+_FILE_OFFSET_BITS\s+.*$")
re_undef_file_offset_bits = re.compile(r"^\s*#\s*undef\s+_FILE_OFFSET_BITS\s*$")
re_flag_time_bits_64 = re.compile(rf"_TIME_BITS={Y2038_SAFE_TIME_BITS}(?:\s|$|;)")
re_flag_time_bits = re.compile(r"_TIME_BITS=(\d+)")
re_flag_use_time_bits64 = re.compile(r"_USE_TIME_BITS64(?:\s|$|=|;)")
re_flag_file_offset_bits_64 = re.compile(
    rf"_FILE_OFFSET_BITS={Y2038_SAFE_FILE_OFFSET_BITS}(?:\s|$|;)"
)
re_flag_file_offset_bits = re.compile(r"_FILE_OFFSET_BITS=(\d+)")
id_Y2038 = {
    "time_t" "lastlog",
    "msqid_ds",
    "semid_ds",
    "timeb",
    "timespec",
    "timeval",
    "utimbuf",
    "itimerspec",
    "clnt_ops",
    "elf_prstatus",
    "itimerval",
    "ntptimeval",
    "rusage",
    "timex",
    "utmp",
    "utmpx",
    "ctime",
    "ctime_r",
    "difftime",
    "gmtime",
    "gmtime_r",
    "localtime",
    "localtime_r",
    "mktime",
    "stime",
    "timegm",
    "timelocal",
    "time",
    "msgctl",
    "ftime",
    "aio_suspend",
    "clock_getres",
    "clock_gettime",
    "clock_nanosleep",
    "clock_settime",
    "futimens",
    "mq_timedreceive",
    "mq_timedsend",
    "nanosleep",
    "pselect",
    "pthread_cond_timedwait",
    "pthread_mutex_timedlock",
    "pthread_rwlock_timedrdlock",
    "pthread_rwlock_timedwrlock",
    "sched_rr_get_interval",
    "sem_timedwait",
    "sigtimedwait",
    "timespec_get",
    "utimensat",
    "adjtime",
    "pmap_rmtcall",
    "clntudp_bufcreate",
    "clntudp_create",
    "futimes",
    "gettimeofday",
    "lutimes",
    "select",
    "settimeofday",
    "utimes",
    "utime",
    "timerfd_gettime",
    "timerfd_settime",
    "timer_gettime",
    "timer_settime",
    "fstatat",
    "fstat",
    "__fxstatat",
    "__fxstat",
    "lstat",
    "__lxstat",
    "stat",
    "__xstat",
    "struct itimerval",
    "setitimer",
    "getitimer",
    "ntp_gettime",
    "getrusage",
    "wait3",
    "wait4",
    "adjtimex",
    "ntp_adjtime",
    "getutent_r",
    "getutent",
    "getutid_r",
    "getutid",
    "getutline_r",
    "getutline",
    "login",
    "pututline",
    "updwtmp",
    "getutxent",
    "getutxid",
    "getutxline",
    "pututxline",
}


def parse_dump_config(config_name):
    """
    Parse Y2038-related flags from cppcheck dump file configuration name.
    This function analyzes the cppcheck dump file configuration name (which contains
    preprocessor definitions extracted by cppcheck from project files like compile_commands.json)
    to extract Y2038-related definitions. It looks for _TIME_BITS, _USE_TIME_BITS64, and
    _FILE_OFFSET_BITS definitions and validates their values.
    Args:
        config_name (str): The cppcheck configuration name from dump file
                          (e.g., "_TIME_BITS=64;_FILE_OFFSET_BITS=64")
    Returns:
        dict: Dictionary containing Y2038-related flag information with keys:
            - 'time_bits_defined' (bool): Whether _TIME_BITS is defined
            - 'time_bits_value' (int|None): Value of _TIME_BITS (None if not defined)
            - 'use_time_bits64_defined' (bool): Whether _USE_TIME_BITS64 is defined
            - 'file_offset_bits_defined' (bool): Whether _FILE_OFFSET_BITS is defined
            - 'file_offset_bits_value' (int|None): Value of _FILE_OFFSET_BITS (None if not defined)
    Example:
        >>> parse_dump_config("_TIME_BITS=64;_FILE_OFFSET_BITS=64")
        {
            'time_bits_defined': True,
            'time_bits_value': 64,
            'use_time_bits64_defined': False,
            'file_offset_bits_defined': True,
            'file_offset_bits_value': 64
        }
    """
    result = {
        "time_bits_defined": False,
        "time_bits_value": None,
        "use_time_bits64_defined": False,
        "file_offset_bits_defined": False,
        "file_offset_bits_value": None,
    }
    if not config_name:
        return result
    try:
        if re_flag_time_bits_64.search(config_name):
            result["time_bits_defined"] = True
            result["time_bits_value"] = Y2038_SAFE_TIME_BITS
        else:
            match = re_flag_time_bits.search(config_name)
            if match:
                result["time_bits_defined"] = True
                try:
                    result["time_bits_value"] = int(match.group(1))
                except (ValueError, IndexError):
                    result["time_bits_defined"] = False
                    result["time_bits_value"] = None
        if re_flag_use_time_bits64.search(config_name):
            result["use_time_bits64_defined"] = True
        if re_flag_file_offset_bits_64.search(config_name):
            result["file_offset_bits_defined"] = True
            result["file_offset_bits_value"] = Y2038_SAFE_FILE_OFFSET_BITS
        else:
            match = re_flag_file_offset_bits.search(config_name)
            if match:
                result["file_offset_bits_defined"] = True
                try:
                    result["file_offset_bits_value"] = int(match.group(1))
                except (ValueError, IndexError):
                    result["file_offset_bits_defined"] = False
                    result["file_offset_bits_value"] = None
    except (AttributeError, TypeError, ValueError):
        pass
    return result


def check_y2038_safe(dumpfile, quiet=False):
    """
    Main function to check Y2038 safety of C/C++ code from cppcheck dump files.
    This function performs comprehensive Y2038 analysis including:
    1. Extraction of Y2038-related compiler flags from cppcheck dump file configuration
    2. Analysis of source code preprocessor directives
    3. Warning suppression when proper Y2038 configuration is detected
    4. Reporting of Y2038-unsafe symbols and configurations
    The function implements a priority-based approach for Y2038 flag detection:
    - Dump file configuration (from cppcheck's project parsing - highest priority)
    - Source code #define directives (fallback)
    Warning suppression occurs when both _TIME_BITS=64 AND _FILE_OFFSET_BITS=64
    are detected from any source. When warnings are suppressed, an informational
    message is displayed indicating the configuration source and suppression count.
    Args:
        dumpfile (str): Path to the cppcheck XML dump file (.dump extension)
        quiet (bool, optional): If True, suppress informational messages. Defaults to False.
    Returns:
        bool: True if code is Y2038-safe, False if Y2038 issues were detected
    Raises:
        Exception: May raise exceptions from cppcheckdata parsing or file I/O operations
    Example:
        >>> check_y2038_safe("test.c.dump")  # Normal operation
        True
        >>> check_y2038_safe("test.c.dump", quiet=True)  # Suppress info messages
        False
    """
    y2038safe = True
    data = cppcheckdata.CppcheckData(dumpfile)
    srcfile = data.files[0]
    for cfg in data.iterconfigurations():
        if not quiet:
            print("Checking %s, config %s..." % (srcfile, cfg.name))
        safe_ranges = []
        safe = -1
        time_bits_defined = False
        srclinenr = 0
        dump_config_flags = parse_dump_config(cfg.name)
        effective_flags = {
            "time_bits_defined": dump_config_flags["time_bits_defined"],
            "time_bits_value": dump_config_flags["time_bits_value"],
            "use_time_bits64_defined": dump_config_flags["use_time_bits64_defined"],
            "file_offset_bits_defined": dump_config_flags["file_offset_bits_defined"],
            "file_offset_bits_value": dump_config_flags["file_offset_bits_value"],
        }
        config_source = None
        has_dump_config = (
            dump_config_flags["time_bits_defined"]
            or dump_config_flags["file_offset_bits_defined"]
            or dump_config_flags["use_time_bits64_defined"]
        )
        if has_dump_config:
            config_source = "cppcheck configuration"
        time_bits_defined = effective_flags["time_bits_defined"]
        if effective_flags["time_bits_defined"]:
            if effective_flags["time_bits_value"] != Y2038_SAFE_TIME_BITS:
                fake_directive = type(
                    "FakeDirective",
                    (),
                    {
                        "file": srcfile,
                        "linenr": 0,
                        "column": 0,
                        "str": "cppcheck configuration: _TIME_BITS=%s"
                        % effective_flags["time_bits_value"],
                    },
                )()
                cppcheckdata.reportError(
                    fake_directive,
                    "error",
                    "_TIME_BITS must be defined equal to 64 (found in cppcheck configuration: _TIME_BITS=%s)"
                    % effective_flags["time_bits_value"],
                    "y2038",
                    "type-bits-not-64",
                )
                y2038safe = False
        if effective_flags["file_offset_bits_defined"]:
            if effective_flags["file_offset_bits_value"] != Y2038_SAFE_FILE_OFFSET_BITS:
                fake_directive = type(
                    "FakeDirective",
                    (),
                    {
                        "file": srcfile,
                        "linenr": 0,
                        "column": 0,
                        "str": "cppcheck configuration: _FILE_OFFSET_BITS=%s"
                        % effective_flags["file_offset_bits_value"],
                    },
                )()
                cppcheckdata.reportError(
                    fake_directive,
                    "error",
                    "_FILE_OFFSET_BITS must be defined equal to 64 (found in cppcheck configuration: _FILE_OFFSET_BITS=%s)"
                    % effective_flags["file_offset_bits_value"],
                    "y2038",
                    "file-offset-bits-not-64",
                )
                y2038safe = False
        if effective_flags["use_time_bits64_defined"]:
            if not time_bits_defined:
                fake_directive = type(
                    "FakeDirective",
                    (),
                    {
                        "file": srcfile,
                        "linenr": 0,
                        "column": 0,
                        "str": "cppcheck configuration: _USE_TIME_BITS64",
                    },
                )()
                cppcheckdata.reportError(
                    fake_directive,
                    "warning",
                    "_USE_TIME_BITS64 is defined in cppcheck configuration but _TIME_BITS was not",
                    "y2038",
                    "type-bits-undef",
                )
                y2038safe = False
            else:
                safe = 0  # Start of file is safe
        source_time_bits_defined = False  # pylint: disable=unused-variable
        source_file_offset_bits_defined = False  # pylint: disable=unused-variable
        source_file_offset_bits_value = None  # pylint: disable=unused-variable
        source_use_time_bits64_defined = False  # pylint: disable=unused-variable
        source_flags_used = {
            "time_bits": False,
            "file_offset_bits": False,
            "use_time_bits64": False,
        }
        for directive in cfg.directives:
            if directive.file == srcfile:
                srclinenr = directive.linenr
            if re_define_time_bits_64.match(directive.str):
                source_time_bits_defined = True
                if not effective_flags["time_bits_defined"]:
                    effective_flags["time_bits_defined"] = True
                    effective_flags["time_bits_value"] = Y2038_SAFE_TIME_BITS
                    time_bits_defined = True
                    source_flags_used["time_bits"] = True
            elif re_define_time_bits.match(directive.str):
                source_time_bits_defined = False
                if not effective_flags["time_bits_defined"]:
                    source_flags_used["time_bits"] = True
                    cppcheckdata.reportError(
                        directive,
                        "error",
                        "_TIME_BITS must be defined equal to 64",
                        "y2038",
                        "type-bits-not-64",
                    )
                    y2038safe = False
            elif re_undef_time_bits.match(directive.str):
                source_time_bits_defined = False
                if not effective_flags["time_bits_defined"]:
                    time_bits_defined = False
                    source_flags_used["time_bits"] = True
            if re_define_file_offset_bits_64.match(directive.str):
                source_file_offset_bits_defined = True
                source_file_offset_bits_value = Y2038_SAFE_FILE_OFFSET_BITS
                if not effective_flags["file_offset_bits_defined"]:
                    effective_flags["file_offset_bits_defined"] = True
                    effective_flags["file_offset_bits_value"] = (
                        Y2038_SAFE_FILE_OFFSET_BITS
                    )
                    source_flags_used["file_offset_bits"] = True
            elif re_define_file_offset_bits.match(directive.str):
                source_file_offset_bits_defined = False
                if not effective_flags["file_offset_bits_defined"]:
                    source_flags_used["file_offset_bits"] = True
                    cppcheckdata.reportError(
                        directive,
                        "error",
                        "_FILE_OFFSET_BITS must be defined equal to 64",
                        "y2038",
                        "file-offset-bits-not-64",
                    )
                    y2038safe = False
            elif re_undef_file_offset_bits.match(directive.str):
                source_file_offset_bits_defined = False
                source_file_offset_bits_value = None
                if not effective_flags["file_offset_bits_defined"]:
                    effective_flags["file_offset_bits_defined"] = False
                    effective_flags["file_offset_bits_value"] = None
                    source_flags_used["file_offset_bits"] = True
            if re_define_use_time_bits64.match(directive.str):
                safe = int(srclinenr)
                source_use_time_bits64_defined = True
                if not effective_flags["use_time_bits64_defined"]:
                    effective_flags["use_time_bits64_defined"] = True
                    source_flags_used["use_time_bits64"] = True
                    if not time_bits_defined:
                        cppcheckdata.reportError(
                            directive,
                            "warning",
                            "_USE_TIME_BITS64 is defined but _TIME_BITS was not",
                            "y2038",
                            "type-bits-undef",
                        )
            elif re_undef_use_time_bits64.match(directive.str):
                unsafe = int(srclinenr)
                source_use_time_bits64_defined = False
                if not effective_flags["use_time_bits64_defined"]:
                    source_flags_used["use_time_bits64"] = True
                if unsafe > safe >= 0:
                    safe_ranges.append((safe, unsafe))
                    safe = -1
        if len(cfg.tokenlist) > 0:
            unsafe = int(cfg.tokenlist[-1].linenr)
            if unsafe > safe >= 0:
                safe_ranges.append((safe, unsafe))
        y2038_safe_config = (
            effective_flags["time_bits_defined"]
            and effective_flags["time_bits_value"] == Y2038_SAFE_TIME_BITS
            and effective_flags["file_offset_bits_defined"]
            and effective_flags["file_offset_bits_value"] == Y2038_SAFE_FILE_OFFSET_BITS
        )
        if y2038_safe_config:
            dump_flags_count = sum(
                [
                    dump_config_flags["time_bits_defined"],
                    dump_config_flags["file_offset_bits_defined"],
                    dump_config_flags["use_time_bits64_defined"],
                ]
            )
            source_flags_count = sum(source_flags_used.values())
            if dump_flags_count > 0 and source_flags_count > 0:
                config_source = "mixed configuration (cppcheck configuration and source code directives)"
            elif dump_flags_count > 0:
                config_source = "cppcheck configuration"
            elif source_flags_count > 0:
                config_source = "source code directives"
            else:
                config_source = "configuration"
        warnings_suppressed = 0
        for token in cfg.tokenlist:
            if token.str in id_Y2038:
                is_in_safe_range = any(
                    lower <= int(token.linenr) <= upper
                    for (lower, upper) in safe_ranges
                )
                if not is_in_safe_range:
                    if y2038_safe_config:
                        warnings_suppressed += 1
                    else:
                        cppcheckdata.reportError(
                            token,
                            "warning",
                            token.str + " is Y2038-unsafe",
                            "y2038",
                            "unsafe-call",
                        )
                        y2038safe = False
            token = token.next
        if warnings_suppressed > 0 and config_source and not quiet:
            print(
                "Y2038 warnings suppressed: Found proper Y2038 configuration in %s (_TIME_BITS=%d and _FILE_OFFSET_BITS=%d)"
                % (config_source, Y2038_SAFE_TIME_BITS, Y2038_SAFE_FILE_OFFSET_BITS)
            )
            print(
                "Suppressed %d Y2038-unsafe function warning(s)" % warnings_suppressed
            )
    return y2038safe


def get_args_parser():
    parser = cppcheckdata.ArgumentParser()
    return parser


if __name__ == "__main__":
    parser = get_args_parser()
    args = parser.parse_args()
    exit_code = 0
    quiet = args.quiet or args.cli
    if not args.dumpfile:
        if not args.quiet:
            print("no input files.")
        sys.exit(0)
    for dumpfile in args.dumpfile:
        if not quiet:
            print("Checking " + dumpfile + "...")
        check_y2038_safe(dumpfile, quiet)
    sys.exit(cppcheckdata.EXIT_CODE)
