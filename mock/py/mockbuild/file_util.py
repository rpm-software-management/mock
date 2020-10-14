# -*- coding: utf-8 -*-
# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
import os
import os.path

from . import exception
from .trace_decorator import getLog, traceLog


@traceLog()
def mkdirIfAbsent(*args):
    for dirName in args:
        getLog().debug("ensuring that dir exists: %s", dirName)
        if not os.path.exists(dirName):
            try:
                getLog().debug("creating dir: %s", dirName)
                os.makedirs(dirName)
            except OSError as e:
                if e.errno != errno.EEXIST:
                    getLog().exception("Could not create dir %s. Error: %s", dirName, e)
                    raise exception.Error("Could not create dir %s. Error: %s" % (dirName, e))


@traceLog()                                                                        
def touch(fileName):
    getLog().debug("touching file: %s", fileName)
    open(fileName, 'a').close()
