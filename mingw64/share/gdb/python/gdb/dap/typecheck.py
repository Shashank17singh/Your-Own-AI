import collections.abc
import functools
import typing


def _check_instance(value, typevar):
    base = typing.get_origin(typevar)
    if base is None:
        return isinstance(value, typevar)
    arg_types = typing.get_args(typevar)
    if base == collections.abc.Mapping or base == typing.Mapping:
        if not isinstance(value, collections.abc.Mapping):
            return False
        assert len(arg_types) == 2
        keytype, valuetype = arg_types
        return all(
            _check_instance(k, keytype) and _check_instance(v, valuetype)
            for k, v in value.items()
        )
    elif base == collections.abc.Sequence or base == typing.Sequence:
        if not isinstance(value, base):
            return False
        if len(arg_types) == 0:
            return True
        assert len(arg_types) == 1
        arg_type = arg_types[0]
        return all(_check_instance(item, arg_type) for item in value)
    elif base == typing.Union:
        return any(_check_instance(value, arg_type) for arg_type in arg_types)
    raise TypeError("unsupported type variable '" + str(typevar) + "'")


def type_check(func):
    """A decorator that checks FUNC's argument types at runtime."""
    if not hasattr(typing, "get_origin"):
        return func
    hints = typing.get_type_hints(func)
    if "return" in hints:
        del hints["return"]

    @functools.wraps(func)
    def check_arguments(**kwargs):
        for key in hints:
            if key in kwargs and not _check_instance(kwargs[key], hints[key]):
                raise TypeError(
                    "value for '"
                    + key
                    + "' does not have expected type '"
                    + str(hints[key])
                    + "'"
                )
        return func(**kwargs)

    return check_arguments
