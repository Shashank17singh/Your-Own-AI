try:
    from _decimal import *
    from _decimal import __doc__, __libmpdec_version__, __version__
except ImportError:
    from _pydecimal import *
