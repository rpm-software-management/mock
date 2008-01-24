# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# License: GPL2 or later see COPYING
# Written by Michael Brown
# Sections by Seth Vidal
# Sections taken from Mach by Thomas Vander Stichele
# Copyright (C) 2007 Michael E Brown <mebrown@michaels-house.net>

# python library imports
import ctypes
import os
import os.path
import popen2
import rpm
import rpmUtils
import rpmUtils.transaction
import select
import shutil
import signal
import subprocess
import time

# our imports
import mock.exception
from mock.trace_decorator import traceLog, decorate, getLog
import mock.uid as uid

_libc = ctypes.cdll.LoadLibrary(None)
_errno = ctypes.c_int.in_dll(_libc, "errno")
_libc.personality.argtypes = [ctypes.c_ulong]
_libc.personality.restype = ctypes.c_int
_libc.unshare.argtypes = [ctypes.c_int,]
_libc.unshare.restype = ctypes.c_int
CLONE_NEWNS = 0x00020000

# taken from sys/personality.h
PER_LINUX32=0x0008
PER_LINUX=0x0000
personality_defs = {
    'x86_64': PER_LINUX, 'ppc64': PER_LINUX, 'sparc64': PER_LINUX,
    'i386': PER_LINUX32, 'i586': PER_LINUX32, 'i686': PER_LINUX32,
    'ppc': PER_LINUX32, 'sparc': PER_LINUX32, 'sparcv9': PER_LINUX32,
    'ia64' : PER_LINUX, 'alpha' : PER_LINUX,
}

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
            if os.path.realpath(root) == os.path.realpath(rootToKill):
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

# not traced...
def chomp(line):
    if line.endswith("\n"):
        return line[:-1]
    else:
        return line

decorate(traceLog())
def unshare(flags):
    getLog().debug("Unsharing. Flags: %s" % flags)
    try:
        res = _libc.unshare(flags)
        if res:
            raise OSError(_errno.value, os.strerror(_errno.value))
    except AttributeError, e:
        pass

# these are called in child process, so no logging
def condChroot(chrootPath):
    if chrootPath is not None:
        saved = { "ruid": os.getuid(), "euid": os.geteuid(), }
        uid.setresuid(0,0,0)
        os.chdir(chrootPath)
        os.chroot(chrootPath)
        uid.setresuid(saved['ruid'], saved['euid'])

def condChdir(cwd):
    if cwd is not None:
        os.chdir(cwd)

def condDropPrivs(uid, gid):
    if gid is not None:
        os.setregid(gid, gid)
    if uid is not None:
        os.setreuid(uid, uid)

def condPersonality(per=None):
    if per is None or per in ('noarch',):
        return
    if personality_defs.get(per, None) is None:
        return
    res = _libc.personality(personality_defs[per])
    if res == -1:
        raise OSError(_errno.value, os.strerror(_errno.value))


def logOutput(fds, logger, returnOutput=1, start=0, timeout=0):
    output=""
    done = 0
    while not done:
        if (time.time() - start)>timeout and timeout!=0:
            done = 1
            break

        i_rdy,o_rdy,e_rdy = select.select(fds,[],[],1) 
        for s in i_rdy:
            # this isnt perfect as a whole line of input may not be
            # ready, but should be "good enough" for now
            line = s.readline()
            if line == "":
                done = 1
                break
            logger.debug(chomp(line))
            if returnOutput:
                output += line
    return output

# logger =
# output = [1|0]
# chrootPath
#
# The "Not-as-complicated" version
#
decorate(traceLog())
def do(command, shell=False, chrootPath=None, cwd=None, timeout=0, raiseExc=True, returnOutput=0, uid=None, gid=None, personality=None, *args, **kargs):

    logger = kargs.get("logger", getLog())
    output = ""
    start = time.time()
    preexec = ChildPreExec(personality, chrootPath, cwd, uid, gid)
    try:
        child = None
        logger.debug("Executing command: %s" % command)
        child = subprocess.Popen(
            command, 
            shell=shell,
            bufsize=0, close_fds=True, 
            stdin=open("/dev/null", "r"), 
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn = preexec,
            )

        # use select() to poll for output so we dont block
        output = logOutput([child.stdout, child.stderr], 
                           logger, returnOutput, start, timeout)

    except:
        # kill children if they arent done
        if child is not None and child.returncode is None:
            os.kill(-child.pid, 15)
            os.kill(-child.pid, 9)
        raise

    # wait until child is done, kill it if it passes timeout
    while child.poll() is None:
        if (time.time() - start)>timeout and timeout!=0:
            os.kill(-child.pid, 15)
            os.kill(-child.pid, 9)
            raise commandTimeoutExpired, ("Timeout(%s) expired for command:\n # %s\n%s" % (command, output))


    if raiseExc and child.returncode:
        if returnOutput:
            raise mock.exception.Error, ("Command failed: \n # %s\n%s" % (command, output), child.returncode)
        else:
            raise mock.exception.Error, ("Command failed. See logs for output.\n # %s" % (command,), child.returncode)

    return output

class ChildPreExec(object):
    def __init__(self, personality, chrootPath, cwd, uid, gid):
        self.personality = personality
        self.chrootPath  = chrootPath
        self.cwd = cwd
        self.uid = uid
        self.gid = gid

    def __call__(self, *args, **kargs):
        os.setpgrp()
        condPersonality(self.personality)
        condChroot(self.chrootPath)
        condDropPrivs(self.uid, self.gid)
        condChdir(self.cwd)
