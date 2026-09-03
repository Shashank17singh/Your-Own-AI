#ifndef __MSPBASE_H_
#define __MSPBASE_H_
#define _ATL_FREE_THREADED
#include <atlbase.h>
extern CComModule _Module;
#include <atlcom.h>
#include <control.h>
#include <msp.h>
#include <strmif.h>
#include <tapi.h>
#include <tapi3err.h>
#include <tapi3if.h>
#include <termmgr.h>
#include <uuids.h>
EXTERN_C const IID LIBID_TAPI3Lib;
#include "mspaddr.h"
#include "mspcall.h"
#include "mspcoll.h"
#include "mspenum.h"
#include "msplog.h"
#include "mspstrm.h"
#include "mspterm.h"
#include "mspthrd.h"
#include "msptrmac.h"
#include "msptrmar.h"
#include "msptrmvc.h"
#include "msputils.h"
#endif
