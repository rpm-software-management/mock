# -*- coding: utf-8 -*-
# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# License: GPL2 or later see COPYING
# Written by Michael Brown
# Copyright (C) 2007 Michael E Brown <mebrown@michaels-house.net>

import functools
import inspect
import logging
import os
import sys


# defaults to module verbose log
# does a late binding on log. Forwards all attributes to logger.
# works around problem where reconfiguring the logging module means loggers
# configured before reconfig dont output.
class getLog(object):
    # pylint: disable=unused-argument,too-few-public-methods
    def __init__(self, name=None, prefix="", *args, **kargs):
        if name is None:
            frame = inspect.getouterframes(inspect.currentframe())[1][0]
            name = frame.f_globals["__name__"]

        self.name = prefix + name

    def __getattr__(self, name):
        logger = logging.getLogger(self.name)
        return getattr(logger, name)


# emulates logic in logging module to ensure we only log
# messages that logger is enabled to produce.
def doLog(logger, level, *args, **kargs):
    if logger.manager.disable >= level:
        return
    if logger.isEnabledFor(level):
        try:
            logger.handle(logger.makeRecord(logger.name, level, *args, **kargs))
        except TypeError:
            del(kargs["func"])
            logger.handle(logger.makeRecord(logger.name, level, *args, **kargs))


def safe_repr(arg):
    """ Generally repr() can fail when called before __init__(), we will workaround this case """
    try:
        return repr(arg)
    except AttributeError:
        return str(type(arg))

def traceLog(logger=None):
    def noop(func):
        return func

    def decorator(func):
        @functools.wraps(func)
        def trace(*args, **kw):
            # default to logger that was passed by module, but
            # can override by passing logger=foo as function parameter.
            # make sure this doesn't conflict with one of the parameters
            # you are expecting

            filename = os.path.normcase(inspect.getsourcefile(func))
            func_name = func.__name__
            if hasattr(func, 'func_code'):
                lineno = func.func_code.co_firstlineno
            else:
                lineno = func.__code__.co_firstlineno

            l2 = kw.get('logger', logger)
            if l2 is None:
                l2 = logging.getLogger("trace.%s" % func.__module__)
            if isinstance(l2, str):
                l2 = logging.getLogger(l2)

            message = "ENTER %s("
            message = message + ', '.join([safe_repr(arg) for arg in args])
            if args and kw:
                message += ', '
            for k, v in list(kw.items()):
                message = message + "%s=%s" % (k, safe_repr(v))
            message = message + ")"

            frame = inspect.getouterframes(inspect.currentframe())[1][0]
            doLog(l2, logging.INFO, os.path.normcase(frame.f_code.co_filename),
                  frame.f_lineno, message, args=[func_name], exc_info=None,
                  func=frame.f_code.co_name)
            try:
                result = "Bad exception raised: Exception was not a derived "\
                         "class of 'Exception'"
                try:
                    result = func(*args, **kw)
                except (KeyboardInterrupt, Exception) as e:
                    result = "EXCEPTION RAISED"
                    doLog(l2, logging.INFO, filename, lineno,
                          "EXCEPTION: %s\n", args=[e],
                          exc_info=sys.exc_info(), func=func_name)
                    raise
            finally:
                doLog(l2, logging.INFO, filename, lineno,
                      "LEAVE %s --> %s\n", args=[func_name, result],
                      exc_info=None, func=func_name)

            return result
        return trace
        #end of trace()

    if os.environ.get("MOCK_TRACE_LOG", "true") == "false":
        return noop

    if logging.getLogger("trace").propagate:
        return decorator
    else:
        return noop


# unit tests...
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.WARNING,
        format='%(name)s %(levelname)s %(filename)s, %(funcName)s, Line: %(lineno)d:  %(message)s',)
    log = getLog("foobar.bubble")
    root = getLog(name="")
    log.setLevel(logging.WARNING)
    root.setLevel(logging.DEBUG)

    log.debug(" --> debug")
    log.error(" --> error")
    log.warning(" --> warning")

    @traceLog(log)
    # pylint: disable=unused-argument
    def testFunc(arg1, arg2="default", *args, **kargs):
        return 42

    testFunc("hello", "world", logger=root)
    testFunc("happy", "joy", name="skippy")
    testFunc("hi")

    @traceLog(root)
    def testFunc22():
        return testFunc("archie", "bunker")

    testFunc22()

    @traceLog(root)
    def testGen():
        yield 1
        yield 2

    for j in testGen():
        log.debug("got: %s", j)

    @traceLog()
    def anotherFunc(*args):
        # pylint: disable=no-value-for-parameter
        return testFunc(*args)

    anotherFunc("pretty")

    getLog()
