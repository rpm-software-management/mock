# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# License: GPL2 or later see COPYING
# Written by Michael Brown
# Sections by Seth Vidal
# Sections taken from Mach by Thomas Vander Stichele
# Copyright (C) 2007 Michael E Brown <mebrown@michaels-house.net>

# python library imports
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
from mock.trace_decorator import traceLog, decorate, getLog

# classes
class commandTimeoutExpired(mock.exception.Error):
    def __init__(self, msg):
        mock.exception.Error.__init__(self, msg)
        self.msg = msg
        self.resultcode = 10

# functions
decorate(traceLog())
def mkdirIfAbsent(*args):
    for dirName in args:
        getLog().debug("ensuring that dir exists: %s" % dirName)
        if not os.path.exists(dirName):
            try:
                getLog().debug("creating dir: %s" % dirName)
                os.makedirs(dirName)
            except OSError, e:
                getLog().exception("Could not create dir %s. Error: %s" % (dirName, e))
                raise mock.exception.Error, "Could not create dir %s. Error: %s" % (dirName, e)

decorate(traceLog())
def touch(fileName):
    getLog().debug("touching file: %s" % fileName)
    fo = open(fileName, 'w')
    fo.close()

decorate(traceLog())
def rmtree(path, *args, **kargs):
    """version os shutil.rmtree that ignores no-such-file-or-directory errors,
       and tries harder if it finds immutable files"""
    tryAgain = 1
    failedFilename = None
    getLog().debug("remove tree: %s" % path)
    while tryAgain:
        tryAgain = 0
        try:
            shutil.rmtree(path, *args, **kargs)
        except OSError, e:
            if e.errno == 2: # no such file or directory
                pass
            elif e.errno==1 or e.errno==13:
                tryAgain = 1
                if failedFilename == e.filename:
                    raise
                failedFilename = e.filename
                os.system("chattr -R -i %s" % path)
            else:
                raise

decorate(traceLog())
def orphansKill(rootToKill):
    """kill off anything that is still chrooted."""
    getLog().debug("kill orphans")
    for fn in os.listdir("/proc"):
        try:
            root = os.readlink("/proc/%s/root" % fn)
            if root == rootToKill:
                getLog().warning("Process ID %s still running in chroot. Killing..." % fn)
                os.kill(int(fn, 10), 15)
        except OSError, e:
            pass


decorate(traceLog())
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

decorate(traceLog())
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

decorate(traceLog())
def getNEVRA(hdr):
    name = hdr[rpm.RPMTAG_NAME]
    ver  = hdr[rpm.RPMTAG_VERSION]
    rel  = hdr[rpm.RPMTAG_RELEASE]
    epoch = hdr[rpm.RPMTAG_EPOCH]
    arch = hdr[rpm.RPMTAG_ARCH]
    if epoch is None: epoch = 0
    return (name, epoch, ver, rel, arch)

decorate(traceLog())
def getAddtlReqs(hdr, conf):
    # Add the 'more_buildreqs' for this SRPM (if defined in config file)
    (name, epoch, ver, rel, arch) = getNEVRA(hdr)
    reqlist = []
    for this_srpm in ['-'.join([name, ver, rel]),
                      '-'.join([name, ver]),
                      '-'.join([name]),]:
        if conf.has_key(this_srpm):
            more_reqs = conf[this_srpm]
            if type(more_reqs) in (type(u''), type(''),):
                reqlist.append(more_reqs)
            else:
                reqlist.extend(more_reqs)
            break

    return rpmUtils.miscutils.unique(reqlist)

decorate(traceLog())
def uniqReqs(*args):
    master = []
    for l in args:
        master.extend(l)
    return rpmUtils.miscutils.unique(master)

decorate(traceLog())
def condChroot(chrootPath, uidManager=None):
    if chrootPath is not None:
        getLog().debug("chroot %s" % chrootPath)
        if uidManager:
            getLog().debug("elevate privs to run chroot")
            uidManager.becomeUser(0)
        os.chdir(chrootPath)
        os.chroot(chrootPath)
        if uidManager:
            getLog().debug("back to other privs")
            uidManager.restorePrivs()

decorate(traceLog())
def condDropPrivs(uidManager, uid, gid):
    if uidManager is not None:
        getLog().debug("about to drop privs")
        if uid is not None:
            uidManager.unprivUid = uid
        if gid is not None:
            uidManager.unprivGid = gid
        uidManager.dropPrivsForever()

# not traced...
def chomp(line):
    if line.endswith("\n"):
        return line[:-1]
    else:
        return line

# taken from sys/personality.h
PER_LINUX32=0x0008
PER_LINUX=0x0000
personality_defs = {
    'x86_64': PER_LINUX, 'ppc64': PER_LINUX, 'sparc64': PER_LINUX,
    'i386': PER_LINUX32, 'i586': PER_LINUX32, 'i686': PER_LINUX32, 
    'ppc': PER_LINUX32, 'sparc': PER_LINUX32, 'sparcv9': PER_LINUX32,
}

import ctypes
_libc = ctypes.cdll.LoadLibrary("libc.so.6")
_errno = ctypes.c_int.in_dll(_libc, "errno")
_libc.personality.argtypes = [ctypes.c_ulong]
_libc.personality.restype = ctypes.c_int

decorate(traceLog())
def condPersonality(per=None):
    if per is None:
        return
    if personality_defs.get(per, None) is None:
        getLog().warning("Unable to find predefined setarch personality constant for '%s' arch."
            " You may have to manually run setarch."% per)
        return
    res = _libc.personality(personality_defs[per])
    if res == -1:
        raise OSError(_errno.value, os.strerror(_errno.value))
    getLog().debug("Ran setarch '%s'" % per)

CLONE_NEWNS = 0x00020000

decorate(traceLog())
def unshare(flags):
    getLog().debug("Unsharing. Flags: %s" % flags)
    try:
        _libc.unshare.argtypes = [ctypes.c_int,]
        _libc.unshare.restype = ctypes.c_int
        res = _libc.unshare(flags)
        if res:
            raise OSError(_errno.value, os.strerror(_errno.value))
    except AttributeError, e:
        pass

# logger =
# output = [1|0]
# chrootPath
#
# Warning: this is the function from hell. :(
#
decorate(traceLog())
def do(command, chrootPath=None, timeout=0, raiseExc=True, returnOutput=0, uidManager=None, uid=None, gid=None, personality=None, *args, **kargs):
    """execute given command outside of chroot"""

    logger = kargs.get("logger", getLog())
    logger.debug("run cmd timeout(%s): %s" % (timeout, command))

    def alarmhandler(signum, stackframe):
        raise commandTimeoutExpired("Timeout(%s) exceeded for command: %s" % (timeout, command))

    retval = 0

    output = ""
    (r, w) = os.pipe()
    pid = os.fork()
    if pid: #parent
        rpid = ret = 0
        os.close(w)
        oldhandler = signal.signal(signal.SIGALRM, alarmhandler)
        # timeout=0 means disable alarm signal. no timeout
        signal.alarm(timeout)

        try:
            # read output from child
            r_fh = os.fdopen(r, "r")
            for line in r_fh:
                logger.debug(chomp(line))

                if returnOutput:
                    output += line

            # close read handle, get child return status, etc
            r_fh.close()
            (rpid, ret) = os.waitpid(pid, 0)
            signal.alarm(0)
            signal.signal(signal.SIGALRM, oldhandler)

        # kill children for any exception...
        finally:
            try:
                os.kill(-pid, signal.SIGTERM)
                time.sleep(1)
                os.kill(-pid, signal.SIGKILL)
            except OSError:
                pass
            signal.signal(signal.SIGALRM, oldhandler)

        # mask and return just return value, plus child output
        if raiseExc and ((os.WIFEXITED(ret) and os.WEXITSTATUS(ret)) or os.WIFSIGNALED(ret)):
            if returnOutput:
                raise mock.exception.Error, ("Command failed: \n # %s\n%s" % (command, output), ret)
            else:
                raise mock.exception.Error, ("Command failed. See logs for output.\n # %s" % (command,), ret)

        return output

    else: #child
        retval = 255
        try:
            os.close(r)
            # become process group leader so that our parent
            # can kill our children
            os.setpgrp()

            condPersonality(personality)
            condChroot(chrootPath, uidManager)
            condDropPrivs(uidManager, uid, gid)

            child = popen2.Popen4(command)
            child.tochild.close()

            w = os.fdopen(w, "w")
            for line in child.fromchild:
                w.write(line)
                w.flush()
            w.close()
            retval = child.wait()
        finally:
            os._exit(os.WEXITSTATUS(retval))
