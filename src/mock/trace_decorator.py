# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:

import types
from decorator import decorator

import logging
log = logging.getLogger("function_tracing")

#@decorator
@decorator
def trace(f, *args, **kw):
    log.debug("ENTER: %s(%s, %s)\n" % (f.func_name, args, kw))
    try:
        result = "Bad exception raised: Exception was not a derived class of 'Exception'"
        try:
            result = f(*args, **kw)
        except Exception, e:
            result = "EXCEPTION RAISED"
            log.debug( "EXCEPTION: %s\n" % e, exc_info=1)
            raise
    finally:
        log.debug( "LEAVE %s --> %s\n\n" % (f.func_name, result))

    return result

# helper function so we can use back-compat format but not be ugly
def decorateAllFunctions(module):
    methods = [ method for method in dir(module)
            if isinstance(getattr(module, method), types.FunctionType)
            ]
    for i in methods:
        setattr(module, i, trace(getattr(module,i)))

