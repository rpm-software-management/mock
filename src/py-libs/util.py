#!/usr/bin/python -tt
# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
# Written by Seth Vidal
# Sections taken from Mach by Thomas Vander Stichele
# revised and adapted by Michael Brown

# python library imports
import logging
import os
import os.path
import popen2
import rpm
import rpmUtils
import rpmUtils.transaction
import shutil
import signal
import time

# our imports
import mock.exception
from mock.trace_decorator import traceLog

# set up logging
log = logging.getLogger("mock.util")

# classes
class commandTimeoutExpired(mock.exception.Error):
    def __init__(self, msg):
        Error.__init__(self, msg)
        self.msg = msg
        self.resultcode = 10

# functions
@traceLog(log)
def mkdirIfAbsent(*args):
    for dir in args:
        log.debug("ensuring that dir exists: %s" % dir)
        if not os.path.exists(dir):
            try:
                log.debug("creating dir: %s" % dir)
                os.makedirs(dir)
            except OSError, e:
                log.exception("Could not create dir %s. Error: %s" % (dir, e))
                raise mock.exception.Error, "Could not create dir %s. Error: %s" % (dir, e)

@traceLog(log)
def touch(fileName):
    log.debug("touching file: %s" % fileName)
    fo = open(fileName, 'w')
    fo.close()

@traceLog(log)
def rmtree(*args, **kargs):
    """version os shutil.rmtree that ignores no-such-file-or-directory errors"""
    try:
        shutil.rmtree(*args, **kargs)
    except OSError, e:
        if e.errno != 2: # no such file or directory
            raise

@traceLog(log)
def getSrpmHeader(srpms):
    ts = rpmUtils.transaction.initReadOnlyTransaction()
    for srpm in srpms:
        try:
            hdr = rpmUtils.miscutils.hdrFromPackage(ts, srpm)
        except (rpmUtils.RpmUtilsError,), e:
            raise mock.exception.Error, "Cannot find/open srpm: %s. Error: %s" % (srpm, ''.join(e))

        if hdr[rpm.RPMTAG_SOURCEPACKAGE] != 1:
            raise mock.exception.Error("File is not an srpm: %s." % srpm )

        yield hdr

@traceLog(log)
def do_interactive(command, *args, **kargs):
    # we always assume that we dont care about return code for interactive stuff
    os.system(command)

@traceLog(log)
def do(command, timeout=0, raiseExc=True, interactive=0, *args, **kargs):
    """execute given command outside of chroot"""
    log.debug("Run cmd: %s" % command)

    # need to not fork, etc or interactive command wont properly display, so catch it here.
    if interactive:
        return do_interactive(command, timeout=timeout, raiseExc=raiseExc, *args, **kargs)

    class alarmExc(Exception): pass
    def alarmhandler(signum,stackframe):
        raise alarmExc("timeout expired")
    
    retval = 0
    log.debug("Executing timeout(%s): %s" % (timeout, command))

    output=""
    (r,w) = os.pipe()
    pid = os.fork()
    if pid: #parent
        rpid = ret = 0
        os.close(w)
        oldhandler=signal.signal(signal.SIGALRM,alarmhandler)
        starttime = time.time()
        # timeout=0 means disable alarm signal. no timeout
        signal.alarm(timeout)

        try:
            # read output from child
            r_fh = os.fdopen(r, "r")
            for line in r_fh:
                log.debug(line)
                output += line

            # close read handle, get child return status, etc
            r_fh.close()
            (rpid, ret) = os.waitpid(pid, 0)
            signal.alarm(0)
            signal.signal(signal.SIGALRM,oldhandler)

        except alarmExc:
            os.kill(-pid, signal.SIGTERM)
            time.sleep(1)
            os.kill(-pid, signal.SIGKILL)
            (rpid, ret) = os.waitpid(pid, 0)
            signal.signal(signal.SIGALRM,oldhandler)
            raise commandTimeoutExpired( "Timeout(%s) exceeded for command: %s" % (timeout, command))

        # kill children for any exception...
        except:
            os.kill(-pid, signal.SIGTERM)
            time.sleep(1)
            os.kill(-pid, signal.SIGKILL)
            (rpid, ret) = os.waitpid(pid, 0)
            signal.signal(signal.SIGALRM,oldhandler)
            raise

        # mask and return just return value, plus child output
        if raiseExc and os.WEXITSTATUS(ret):
            raise mock.exception.Error, "Command(%s) failed. Output: %s" % (command, output)

        return output

    else: #child
        os.close(r)
        # become process group leader so that our parent
        # can kill our children
        os.setpgrp()  

        child = popen2.Popen4(command)
        child.tochild.close()

        w = os.fdopen(w, "w")
        for line in child.fromchild:
            w.write(line)
            w.flush()
        w.close()
        retval=child.wait()
        os._exit(os.WEXITSTATUS(retval)) 



