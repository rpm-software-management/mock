# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:

import types
from decorator import decorator

import logging
moduleLog = logging.getLogger("mock.trace_decorator")

@decorator
def trace(f, *args, **kw):
    moduleLog.debug("ENTER: %s(%s, %s)" % (f.func_name, args, kw))
    try:
        result = "Bad exception raised: Exception was not a derived class of 'Exception'"
        try:
            result = f(*args, **kw)
        except Exception, e:
            result = "EXCEPTION RAISED"
            moduleLog.debug( "EXCEPTION: %s\n" % e, exc_info=1)
            raise
    finally:
        moduleLog.debug( "LEAVE %s --> %s\n" % (f.func_name, result))

    return result

def traceLog(logger = moduleLog):
    log = logger
    @decorator
    def trace(f, *args, **kw):
        # default to logger that was passed by module, but
        # can override by passing logger=foo as function parameter.
        # make sure this doesnt conflict with one of the parameters
        # you are expecting
        l2 = kw.get('logger', log)
        l2.debug("ENTER: %s(%s, %s)" % (f.func_name, args, kw))
        try:
            result = "Bad exception raised: Exception was not a derived class of 'Exception'"
            try:
                result = f(*args, **kw)
            except Exception, e:
                result = "EXCEPTION RAISED"
                l2.debug( "EXCEPTION: %s\n" % e, exc_info=1)
                raise
        finally:
            l2.debug( "LEAVE %s --> %s\n" % (f.func_name, result))

        return result
    return trace

