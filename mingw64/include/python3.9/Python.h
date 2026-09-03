#ifndef Py_PYTHON_H
#define Py_PYTHON_H
/* Since this is a "meta-include" file, no #ifdef __cplusplus / extern "C" { */

/* Include nearly all Python header files */

#include "patchlevel.h"
#include "pyconfig.h"
#include "pymacconfig.h"

#include <limits.h>

#ifndef UCHAR_MAX
#error "Something's broken.  UCHAR_MAX should be defined in limits.h."
#endif

#if UCHAR_MAX != 255
#error "Python's source code assumes C's unsigned char is an 8-bit type."
#endif

#if defined(__sgi) && !defined(_SGI_MP_SOURCE)
#define _SGI_MP_SOURCE
#endif

#include <stdio.h>
#ifndef NULL
#error "Python.h requires that stdio.h define NULL."
#endif

#include <string.h>
#ifdef HAVE_ERRNO_H
#include <errno.h>
#endif
#include <stdlib.h>
#ifndef MS_WINDOWS
#include <unistd.h>
#endif
#ifdef HAVE_CRYPT_H
#if defined(HAVE_CRYPT_R) && !defined(_GNU_SOURCE)
/* Required for glibc to expose the crypt_r() function prototype. */
#define _GNU_SOURCE
#define _Py_GNU_SOURCE_FOR_CRYPT
#endif
#include <crypt.h>
#ifdef _Py_GNU_SOURCE_FOR_CRYPT
/* Don't leak the _GNU_SOURCE define to other headers. */
#undef _GNU_SOURCE
#undef _Py_GNU_SOURCE_FOR_CRYPT
#endif
#endif

/* For size_t? */
#ifdef HAVE_STDDEF_H
#include <stddef.h>
#endif

/* CAUTION:  Build setups should ensure that NDEBUG is defined on the
 * compiler command line when building Python in release mode; else
 * assert() calls won't be removed.
 */
#include <assert.h>

#include "pymacro.h"
#include "pyport.h"

/* A convenient way for code to know if sanitizers are enabled. */
#if defined(__has_feature)
#if __has_feature(memory_sanitizer)
#if !defined(_Py_MEMORY_SANITIZER)
#define _Py_MEMORY_SANITIZER
#endif
#endif
#if __has_feature(address_sanitizer)
#if !defined(_Py_ADDRESS_SANITIZER)
#define _Py_ADDRESS_SANITIZER
#endif
#endif
#elif defined(__GNUC__)
#if defined(__SANITIZE_ADDRESS__)
#define _Py_ADDRESS_SANITIZER
#endif
#endif

/* Debug-mode build with pymalloc implies PYMALLOC_DEBUG.
 *  PYMALLOC_DEBUG is in error if pymalloc is not in use.
 */
#if defined(Py_DEBUG) && defined(WITH_PYMALLOC) && !defined(PYMALLOC_DEBUG)
#define PYMALLOC_DEBUG
#endif
#if defined(PYMALLOC_DEBUG) && !defined(WITH_PYMALLOC)
#error "PYMALLOC_DEBUG requires WITH_PYMALLOC"
#endif
#include "pymath.h"
#include "pymem.h"
#include "pytime.h"

#include "object.h"
#include "objimpl.h"
#include "pyhash.h"
#include "typeslots.h"

#include "pydebug.h"

#include "boolobject.h"
#include "bytearrayobject.h"
#include "bytesobject.h"
#include "cellobject.h"
#include "classobject.h"
#include "code.h"
#include "complexobject.h"
#include "descrobject.h"
#include "dictobject.h"
#include "enumobject.h"
#include "fileobject.h"
#include "floatobject.h"
#include "funcobject.h"
#include "genericaliasobject.h"
#include "genobject.h"
#include "iterobject.h"
#include "listobject.h"
#include "longintrepr.h"
#include "longobject.h"
#include "memoryobject.h"
#include "methodobject.h"
#include "moduleobject.h"
#include "namespaceobject.h"
#include "odictobject.h"
#include "picklebufobject.h"
#include "pycapsule.h"
#include "pyframe.h"
#include "rangeobject.h"
#include "setobject.h"
#include "sliceobject.h"
#include "structseq.h"
#include "traceback.h"
#include "tupleobject.h"
#include "unicodeobject.h"
#include "warnings.h"
#include "weakrefobject.h"

#include "codecs.h"
#include "pyerrors.h"

#include "context.h"
#include "cpython/initconfig.h"
#include "pystate.h"
#include "pythread.h"

#include "ceval.h"
#include "compile.h"
#include "import.h"
#include "intrcheck.h"
#include "modsupport.h"
#include "osmodule.h"
#include "pyarena.h"
#include "pylifecycle.h"
#include "pythonrun.h"
#include "sysmodule.h"

#include "abstract.h"
#include "bltinmodule.h"

#include "eval.h"

#include "fileutils.h"
#include "pyctype.h"
#include "pyfpe.h"
#include "pystrcmp.h"
#include "pystrtod.h"
#include "tracemalloc.h"

#endif /* !Py_PYTHON_H */
