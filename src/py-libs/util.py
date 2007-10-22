# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# License: GPL2 or later see COPYING
# Written by Michael Brown
# Sections by Seth Vidal
# Sections taken from Mach by Thomas Vander Stichele
# Copyright (C) 2007 Michael E Brown <mebrown@michaels-house.net>

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
def rmtree(path, *args, **kargs):
    """version os shutil.rmtree that ignores no-such-file-or-directory errors, 
       and tries harder if it finds immutable files"""
    tryAgain = 1
    triedTwice = 0
    while tryAgain:
        tryAgain = 0
        try:
            shutil.rmtree(path, *args, **kargs)
        except OSError, e:
            if triedTwice: raise
            if e.errno == 2: # no such file or directory
                pass
            elif e.errno==1:
                tryAgain = 1
                triedTwice = 1
                os.system("chattr -i -R %s" % path)
            else:
                raise

@traceLog(log)
def orphansKill(rootToKill):
    """kill off anything that is still chrooted."""
    for fn in os.listdir("/proc"):
        try:
            root = os.readlink("/proc/%s/root" % fn)
            if root == rootToKill:
                log.warning("Process ID %s still running in chroot. Killing..." % fn)
                os.kill(int(fn,10), 15)
        except OSError, e:
            pass
            

@traceLog(log)
def yieldSrpmHeaders(srpms, plainRpmOk=0):
    ts = rpmUtils.transaction.initReadOnlyTransaction()
    for srpm in srpms:
        try:
            hdr = rpmUtils.miscutils.hdrFromPackage(ts, srpm)
        except (rpmUtils.RpmUtilsError,), e:
            raise mock.exception.Error, "Cannot find/open srpm: %s. Error: %s" % (srpm, ''.join(e))

        if not plainRpmOk and hdr[rpm.RPMTAG_SOURCEPACKAGE] != 1:
            raise mock.exception.Error("File is not an srpm: %s." % srpm )

        yield hdr

@traceLog(log)
def requiresTextFromHdr(hdr):
    """take a header and hand back a unique'd list of the requires as
       strings"""

    reqlist = []
    names = hdr[rpm.RPMTAG_REQUIRENAME]
    flags = hdr[rpm.RPMTAG_REQUIREFLAGS]
    ver = hdr[rpm.RPMTAG_REQUIREVERSION]
    if names is not None:
        tmplst = zip(names, flags, ver)

    for (n, f, v) in tmplst:
        if n.startswith('rpmlib'):
            continue

        req = rpmUtils.miscutils.formatRequire(n, v, f)
        reqlist.append(req)

    return rpmUtils.miscutils.unique(reqlist)

@traceLog(log)
def getNEVRA(hdr):
    name = hdr[rpm.RPMTAG_NAME]
    ver  = hdr[rpm.RPMTAG_VERSION]
    rel  = hdr[rpm.RPMTAG_RELEASE]
    epoch = hdr[rpm.RPMTAG_EPOCH]
    arch = hdr[rpm.RPMTAG_ARCH]
    if epoch is None: epoch = 0
    return (name, epoch, ver, rel, arch)

@traceLog(log)
def getAddtlReqs(hdr, conf):
    # Add the 'more_buildreqs' for this SRPM (if defined in config file)
    (name, epoch, ver, rel, arch) = getNEVRA(hdr)
    reqlist = []
    for this_srpm in ['-'.join([name,ver,rel]),
                      '-'.join([name,ver]),
                      '-'.join([name]),]:
        if conf.has_key(this_srpm):
            more_reqs = conf[this_srpm]
            if type(more_reqs) in (type(u''), type(''),):
                reqlist.append(more_reqs)
            else:
                reqlist.extend(more_reqs)
            break

    return rpmUtils.miscutils.unique(reqlist)

@traceLog(log)
def uniqReqs(*args):
    master = []
    for l in args:
        master.extend(l)
    return rpmUtils.miscutils.unique(master)

# logger =
# output = [1|0]
# chrootPath
#
# Warning: this is the function from hell. :(
#
@traceLog(log)
def do(command, chrootPath=None, timeout=0, raiseExc=True, returnOutput=0, *args, **kargs):
    """execute given command outside of chroot"""
    
    logger = kargs.get("logger", log)
    logger.debug("Run cmd: %s" % command)

    class alarmExc(Exception): pass
    def alarmhandler(signum,stackframe):
        raise alarmExc("timeout expired")
    
    retval = 0
    logger.debug("Executing timeout(%s): %s" % (timeout, command))

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
                if line.endswith("\n"):
                    logger.debug(line[:-1])
                else:
                    logger.debug(line)

                if returnOutput:
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

        # kill all children
        try:
            os.kill(-pid, signal.SIGTERM)
        except OSError:
            pass

        # mask and return just return value, plus child output
        if raiseExc and os.WEXITSTATUS(ret):
            if returnOutput:
                raise mock.exception.Error, "Command(%s) failed. Output: %s" % (command, output)
            else:
                raise mock.exception.Error, "Command(%s) failed. See logs for output." % command

        return output

    else: #child
        retval = 255
        try:
            os.close(r)
            # become process group leader so that our parent
            # can kill our children
            os.setpgrp()  

            uidManager = kargs.get("uidManager")

            if chrootPath is not None:
                if uidManager:
                    logger.debug("elevate privs to run chroot")
                    uidManager.becomeUser(0)
                os.chdir(chrootPath)
                os.chroot(chrootPath)
                if uidManager:
                    logger.debug("back to other privs")
                    uidManager.restorePrivs()

            if uidManager:
                logger.debug("about to drop privs")
                uidManager.dropPrivsForever()

            child = popen2.Popen4(command)
            child.tochild.close()

            w = os.fdopen(w, "w")
            for line in child.fromchild:
                w.write(line)
                w.flush()
            w.close()
            retval=child.wait()
        finally:
            os._exit(os.WEXITSTATUS(retval)) 
