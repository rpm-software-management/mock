import unittest
import inspect
import logging

from functools import wraps

from mockbuild import trace_decorator

def getLineno(fn=None):
    if fn:
        return fn.func_code.co_firstlineno
    return inspect.currentframe().f_back.f_lineno

def captureLogging():
    def decorator(fn):
        @wraps(fn)
        def decorated(self):
            saved = logging.getLogger
            try:
                def getLoggerMock(name=None):
                    return name if name else 'test_default'
                trace_decorator.logging.getLogger = getLoggerMock

                captured = []
                def doLogMock(logger, level, *args, **kwargs):
                    captured.append((logger, level, args, kwargs))
                trace_decorator.doLog = doLogMock

                fn(self, captured)

            finally:
                logging.getLogger = saved
        return decorated
    return decorator


filename = __file__
if filename.endswith('.pyc'):
    filename = filename[:-1]

default_logger = 'trace.{0}'.format(__name__)

def exampleFunc(arg1, arg2="default", *args, **kwargs):
    return 42

class MyException(Exception):
    pass

def exampleRaising(arg1, arg2="default", *args, **kwargs):
    raise MyException('test exception')

def exampleGenerator():
    yield 1
    yield 2

def exampleNested(**kwargs):
    return trace_decorator.traceLog()(exampleFunc)('bbb', **kwargs)

class TraceDecoratorTest(unittest.TestCase):
    @captureLogging()
    def test_default_logger(self, captured):
        trace_decorator.traceLog()(exampleFunc)('aaa')

        loggers = [call[0] for call in captured]
        self.assertEqual([default_logger] * 2, loggers)

    @captureLogging()
    def test_string_logger(self, captured):
        trace_decorator.traceLog('fake_logger')(exampleFunc)('aaa')

        loggers = [call[0] for call in captured]
        self.assertEqual(['fake_logger'] * 2, loggers)

    @captureLogging()
    def test_custom_logger(self, captured):
        logger = type('custom_logger', (), {})
        trace_decorator.traceLog(logger)(exampleFunc)('aaa')

        loggers = [call[0] for call in captured]
        self.assertEqual([logger] * 2, loggers)

    @captureLogging()
    def test_custom_logger_fn(self, captured):
        logger = type('custom_logger', (), {})
        trace_decorator.traceLog()(exampleFunc)('aaa', logger=logger)

        loggers = [call[0] for call in captured]
        self.assertEqual([logger] * 2, loggers)

    @captureLogging()
    def test_capture(self, captured):
        trace_decorator.traceLog()(exampleFunc)('aaa')
        callLineno = getLineno() - 1

        expectations = [
                (default_logger, logging.INFO, (filename, callLineno,
                        "ENTER exampleFunc('aaa', 'default', )"),
                    {'exc_info': None, 'args': [], 'func': 'test_capture'}),
                (default_logger, logging.INFO, (filename, getLineno(exampleFunc),
                        "LEAVE exampleFunc --> 42\n"),
                    {'exc_info': None, 'args': [], 'func': 'exampleFunc'})
                ]

        self.assertEqual(expectations, captured)

    @captureLogging()
    def test_exception(self, captured):
        try:
            trace_decorator.traceLog()(exampleRaising)('aaa')
        except MyException:
            pass

        self.assertEqual(3, len(captured))
        msg, kw = captured[1][2][2], captured[1][3]
        self.assertTrue(kw['exc_info'])
        self.assertEquals("EXCEPTION: test exception\n", msg)
        msg = captured[2][2][2]
        self.assertEqual("LEAVE exampleRaising --> EXCEPTION RAISED\n", msg)

    @captureLogging()
    def test_generator(self, captured):
        trace_decorator.traceLog()(exampleGenerator)()

        self.assertEqual(2, len(captured))

        msg = captured[0][2][2]
        self.assertEqual('ENTER exampleGenerator()', msg)
        msg = captured[1][2][2]
        self.assertIn('LEAVE exampleGenerator --> <generator object exampleGenerator at ',
                      msg)

    @captureLogging()
    def test_nested(self, captured):
        trace_decorator.traceLog()(exampleNested)(arg='ggg')

        self.assertEqual(4, len(captured))

        msg = captured[0][2][2]
        self.assertEqual("ENTER exampleNested(arg='ggg')", msg)
        msg = captured[1][2][2]
        self.assertEqual("ENTER exampleFunc('bbb', 'default', arg='ggg')", msg)
        msg = captured[2][2][2]
        self.assertEqual("LEAVE exampleFunc --> 42\n", msg)
        msg = captured[3][2][2]
        self.assertEqual("LEAVE exampleNested --> 42\n", msg)

if __name__ == '__main__':
    unittest.main()
