# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# License: GPL2 or later see COPYING
# Written by Michael Brown
# Copyright (C) 2007 Michael E Brown <mebrown@michaels-house.net>

import logging
import os
import sys
from peak.util.decorators import rewrap

moduleLog = logging.getLogger("mock.trace_decorator")

# emulates logic in logging module to ensure we only log
# messages that logger is enabled to produce.
def doLog(logger, level, *args, **kargs):
    if logger.manager.disable >= level:
        return
    if logger.isEnabledFor(level):
        logger.handle(logger.makeRecord(logger.name, level, *args, **kargs))

def traceLog(log = moduleLog):
    def decorator(func):
        def trace(*args, **kw):
            # default to logger that was passed by module, but
            # can override by passing logger=foo as function parameter.
            # make sure this doesnt conflict with one of the parameters
            # you are expecting
    
            filename = os.path.normcase(func.func_code.co_filename)
            func_name = func.func_code.co_name
            lineno = func.func_code.co_firstlineno
    
            l2 = kw.get('logger', log)
            message = "ENTER %s(" % func_name
            for arg in args:
                message = message + repr(arg) + ", "
            for k,v in kw.items():
                message = message + "%s=%s" % (k,repr(v))
            message = message + ")"
    
            frame = sys._getframe(2)
            doLog(l2, logging.DEBUG, os.path.normcase(frame.f_code.co_filename), frame.f_lineno, message, args=[], exc_info=None, func=frame.f_code.co_name)
            try:
                result = "Bad exception raised: Exception was not a derived class of 'Exception'"
                try:
                    result = func(*args, **kw)
                except (KeyboardInterrupt, Exception), e:
                    result = "EXCEPTION RAISED"
                    doLog(l2, logging.DEBUG, filename, lineno, "EXCEPTION: %s\n" % e, args=[], exc_info=sys.exc_info(), func=func_name)
                    raise
            finally:
                doLog(l2, logging.DEBUG, filename, lineno, "LEAVE %s --> %s\n" % (func_name, result), args=[], exc_info=None, func=func_name)

            return result
        return rewrap(func, trace)
    return decorator

# unit tests...
if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING,
                    format='%(name)s %(levelname)s %(filename)s, %(funcName)s, Line: %(lineno)d:  %(message)s',)
    log = logging.getLogger("foobar.bubble")
    root = logging.getLogger()
    log.setLevel(logging.WARNING)
    root.setLevel(logging.DEBUG)

    log.debug(" --> debug")
    log.error(" --> error")

    @traceLog(log)
    def testFunc(arg1, arg2="default", *args, **kargs):
        return 42

    testFunc("hello", "world", logger=root)
    testFunc("happy", "joy", name="skippy")
    testFunc("hi")

    @traceLog(root)
    def testFunc22():
        return testFunc("archie", "bunker")

    testFunc22()

