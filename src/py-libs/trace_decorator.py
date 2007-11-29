# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# License: GPL2 or later see COPYING
# Written by Michael Brown
# Copyright (C) 2007 Michael E Brown <mebrown@michaels-house.net>

from decorator import decorator

import logging
import os
import sys

moduleLog = logging.getLogger("mock.trace_decorator")

def traceLog(logger = moduleLog):
    log = logger
    @decorator
    def trace(f, *args, **kw):
        # default to logger that was passed by module, but
        # can override by passing logger=foo as function parameter.
        # make sure this doesnt conflict with one of the parameters
        # you are expecting

        filename = os.path.normcase(f.func_code.co_filename)
        func_name = f.func_code.co_name
        lineno = f.func_code.co_firstlineno

        l2 = kw.get('logger', log)
        message = "ENTER %s(" % f.func_name
        for arg in args:
            message = message + repr(arg) + ", "
        for k,v in kw.items():
            message = message + "%s=%s" % (k,repr(v))
        message = message + ")"

        l2.handle(l2.makeRecord(l2.name, logging.DEBUG, filename, lineno, message, args=[], exc_info=None, func=func_name))
        try:
            result = "Bad exception raised: Exception was not a derived class of 'Exception'"
            try:
                result = f(*args, **kw)
            except (KeyboardInterrupt, Exception), e:
                result = "EXCEPTION RAISED"
                l2.handle(l2.makeRecord(l2.name, logging.DEBUG, filename, lineno, "EXCEPTION: %s\n" % e, args=[], exc_info=sys.exc_info(), func=func_name))
                raise
        finally:
            l2.handle(l2.makeRecord(l2.name, logging.DEBUG, filename, lineno, "LEAVE %s --> %s\n" % (f.func_name, result), args=[], exc_info=None, func=func_name))

        return result
    return trace

# unit tests...
if __name__ == "__main__":
    log = logging.getLogger("foobar")
    logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s %(filename)s, %(funcName)s, Line: %(lineno)d:  %(message)s',
                    )

    log.debug(" --> debug")
    log.error(" --> error")

    @traceLog(log)
    def testFunc(arg1, arg2="default", *args, **kargs):
        return 42

    try:
        testFunc("hello", "world")
        testFunc("happy", "joy", name="skippy")
        testFunc("hi")
    except:
        import traceback
        traceback.print_exc()
