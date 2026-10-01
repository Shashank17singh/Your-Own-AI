"""distutils.command

Package containing implementation of all the standard Distutils
commands."""

__all__ = [
    "bdist",
    "bdist_dumb",
    "bdist_rpm",
    "bdist_wininst",
    "build",
    "build_clib",
    "build_ext",
    "build_py",
    "build_scripts",
    "check",
    "clean",
    "install",
    "install_data",
    "install_headers",
    "install_lib",
    "install_scripts",
    "register",
    "sdist",
    "upload",
    # These two are reserved for future use:
    #'bdist_sdux',
    #'bdist_pkgtool',
    # Note:
    # bdist_packager is not included because it only provides
    # an abstract base class
]
