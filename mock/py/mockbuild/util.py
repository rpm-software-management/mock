# -*- coding: utf-8 -*-
# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# License: GPL2 or later see COPYING
# Written by Michael Brown
# Sections by Seth Vidal
# Sections taken from Mach by Thomas Vander Stichele
# Copyright (C) 2007 Michael E Brown <mebrown@michaels-house.net>
from __future__ import print_function

from ast import literal_eval
import atexit
import ctypes
import errno
import fcntl
from glob import glob
import grp
import locale
import logging
import os
import os.path
import pickle
import pwd
import re
import select
import signal
import socket
import stat
import struct
import subprocess
import sys
import tempfile
# pylint: disable=wrong-import-order
import termios
from textwrap import dedent
import time
import uuid

import distro
import jinja2
import six

from . import exception
from .trace_decorator import getLog, traceLog
from .uid import getresuid, setresuid
from pyroute2 import IPRoute
# pylint: disable=useless-import-alias,no-name-in-module
if six.PY2:
    from collections import MutableMapping as MutableMapping
else:
    from collections.abc import MutableMapping as MutableMapping

encoding = locale.getpreferredencoding()

try:
    # pylint: disable=used-before-assignment
    basestring = basestring
except NameError:
    basestring = str

_libc = ctypes.cdll.LoadLibrary(None)
_libc.personality.argtypes = [ctypes.c_ulong]
_libc.personality.restype = ctypes.c_int
_libc.unshare.argtypes = [ctypes.c_int]
_libc.unshare.restype = ctypes.c_int
_libc.sethostname.argtypes = [ctypes.c_char_p, ctypes.c_int]
_libc.sethostname.restype = ctypes.c_int

# See linux/include/sched.h
CLONE_NEWNS = 0x00020000
CLONE_NEWUTS = 0x04000000
CLONE_NEWPID = 0x20000000
CLONE_NEWNET = 0x40000000
CLONE_NEWIPC = 0x08000000

# taken from sys/personality.h
PER_LINUX32 = 0x0008
PER_LINUX = 0x0000
personality_defs = {
    'x86_64': PER_LINUX, 'ppc64': PER_LINUX, 'sparc64': PER_LINUX,
    'i386': PER_LINUX32, 'i586': PER_LINUX32, 'i686': PER_LINUX32,
    'armv7': PER_LINUX32, 'armv7l': PER_LINUX32, 'armv7hl': PER_LINUX32,
    'armv7hnl': PER_LINUX32, 'armv7hcnl': PER_LINUX32,
    'armv7b': PER_LINUX32, 'armv7hb': PER_LINUX32,
    'armv7hnb': PER_LINUX32, 'armv7hcnb': PER_LINUX32,
    'armv8': PER_LINUX32, 'armv8l': PER_LINUX32, 'armv8hl': PER_LINUX32,
    'armv8hnl': PER_LINUX32, 'armv8hcnl': PER_LINUX32,
    'armv8b': PER_LINUX32, 'armv8hb': PER_LINUX32,
    'armv8hnb': PER_LINUX32, 'armv8hcnb': PER_LINUX32,
    'ppc': PER_LINUX32, 'sparc': PER_LINUX32, 'sparcv9': PER_LINUX32,
    'ia64': PER_LINUX, 'alpha': PER_LINUX,
    's390': PER_LINUX32, 's390x': PER_LINUX,
    'mips': PER_LINUX32, 'mipsel': PER_LINUX32,
    'mipsr6': PER_LINUX32, 'mipsr6el': PER_LINUX32,
    'mips64': PER_LINUX, 'mips64el': PER_LINUX,
    'mips64r6': PER_LINUX, 'mips64r6el': PER_LINUX,
}

PLUGIN_LIST = ['tmpfs', 'root_cache', 'yum_cache', 'bind_mount',
               'ccache', 'selinux', 'package_state', 'chroot_scan',
               'lvm_root', 'compress_logs', 'sign', 'pm_request',
               'hw_info']

USE_NSPAWN = False

RHEL_CLONES = ['centos', 'deskos', 'ol', 'rhel', 'scientific']

_OPS_TIMEOUT = 0


class commandTimeoutExpired(exception.Error):
    def __init__(self, msg):
        exception.Error.__init__(self, msg)
        self.msg = msg
        self.resultcode = 10

# pylint: disable=no-member,unsupported-assignment-operation
class TemplatedDictionary(MutableMapping):
    """ Dictionary where __getitem__() is run through Jinja2 template """
    def __init__(self, *args, **kwargs):
        '''Use the object dict'''
        self.__dict__.update(*args, **kwargs)
    # The next five methods are requirements of the ABC.
    def __setitem__(self, key, value):
        self.__dict__[key] = value
    def __getitem__(self, key):
        return self.__render_value(self.__dict__[key])
    def __delitem__(self, key):
        del self.__dict__[key]
    def __iter__(self):
        return iter(self.__dict__)
    def __len__(self):
        return len(self.__dict__)
    # The final two methods aren't required, but nice to have
    def __str__(self):
        '''returns simple dict representation of the mapping'''
        return str(self.__dict__)
    def __repr__(self):
        '''echoes class, id, & reproducible representation in the REPL'''
        return '{}, TemplatedDictionary({})'.format(super(TemplatedDictionary, self).__repr__(),
                                                    self.__dict__)
    def copy(self):
        return TemplatedDictionary(self.__dict__)
    def __render_value(self, value):
        if isinstance(value, basestring):
            return self.__render_string(value)
        elif isinstance(value, list):
            # we cannot use list comprehension here, as we need to NOT modify the list (pointer to list)
            # and we need to modifiy only individual values in the list
            # If we would create new list, we cannot assign to it, which often happens in configs (e.g. plugins)
            for i in range(len(value)): # pylint: disable=consider-using-enumerate
                value[i] = self.__render_value(value[i])
            return value
        elif isinstance(value, dict):
            # we cannot use list comprehension here, same reasoning as for `list` above
            for k in value.keys():
                value[k] = self.__render_value(value[k])
            return value
        else:
            return value
    def __render_string(self, value):
        template = jinja2.Template(value)
        return _to_native(template.render(self.__dict__))


def _to_bytes(obj, encoding='utf-8', errors='strict', nonstring='strict'):
    if isinstance(obj, six.binary_type):
        return obj
    elif isinstance(obj, six.text_type):
        return obj.encode(encoding, errors)
    else:
        if nonstring == 'strict':
            raise TypeError('First argument must be a string')
        raise ValueError('nonstring must be one of: ["strict",]')


def _to_text(obj, encoding='utf-8', errors='strict', nonstring='strict'):
    if isinstance(obj, six.text_type):
        return obj
    elif isinstance(obj, six.binary_type):
        return obj.decode(encoding, errors)
    else:
        if nonstring == 'strict':
            raise TypeError('First argument must be a string')
        raise ValueError('nonstring must be one of: ["strict",]')


if six.PY2:
    _to_native = _to_bytes
else:
    _to_native = _to_text


@traceLog()
def get_proxy_environment(config):
    env = {}
    for proto in ('http', 'https', 'ftp', 'no'):
        key = '%s_proxy' % proto
        value = config.get(key)
        if value:
            env[key] = value
        elif os.getenv(key):
            env[key] = os.getenv(key)
    return env


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


@traceLog()
def rmtree(path, selinux=False, exclude=()):
    """Version of shutil.rmtree that ignores no-such-file-or-directory errors,
       tries harder if it finds immutable files and supports excluding paths"""
    if os.path.islink(path):
        raise OSError("Cannot call rmtree on a symbolic link")
    try_again = True
    retries = 0
    failed_to_handle = False
    failed_filename = None
    if path in exclude:
        return
    while try_again:
        try_again = False
        try:
            names = os.listdir(path)
            for name in names:
                fullname = os.path.join(path, name)
                if fullname not in exclude:
                    try:
                        mode = os.lstat(fullname).st_mode
                    except OSError:
                        mode = 0
                    if stat.S_ISDIR(mode):
                        try:
                            rmtree(fullname, selinux=selinux, exclude=exclude)
                        except OSError as e:
                            if e.errno in (errno.EPERM, errno.EACCES, errno.EBUSY):
                                # we alrady tried handling this on lower level and failed,
                                # there's no point in trying again now
                                failed_to_handle = True
                            raise
                    else:
                        os.remove(fullname)
            os.rmdir(path)
        except OSError as e:
            if failed_to_handle:
                raise
            if e.errno == errno.ENOENT:  # no such file or directory
                pass
            elif exclude and e.errno == errno.ENOTEMPTY:  # there's something excluded left
                pass
            elif selinux and (e.errno == errno.EPERM or e.errno == errno.EACCES):
                try_again = True
                if failed_filename == e.filename:
                    raise
                failed_filename = e.filename
                os.system("chattr -R -i %s" % path)
            elif e.errno == errno.EBUSY:
                retries += 1
                if retries > 1:
                    raise
                try_again = True
                getLog().debug("retrying failed tree remove after sleeping a bit")
                time.sleep(2)
            else:
                raise


def _safe_check_output(*args):
    # this can be done in one call in python3, but python2 requires this hack
    try:
        output = subprocess.check_output(*args, shell=False, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        output = str(e.output)
    return output


@traceLog()
def get_machinectl_uuid(chroot_path):
    """ Get UUID from machinectl. This function does not check if NSPAWN is used """
    # we will ignore errors in machinectl, it sometimes fails for various errors (cannot find IP addr...)
    # we do not care about exit code, we just want the output
    # RHEL7 does not know --no-legend, so we must filter the legend out
    vm_list = _safe_check_output(["/usr/bin/machinectl", "list", "--no-pager"])
    if (isinstance(vm_list, bytes)):
        vm_list = vm_list.decode("utf-8")
    vm_list = '\n'.join(vm_list.split('\n')[1:-2])
    for name in vm_list.split("\n"):
        if len(name) > 0:
            m_uuid = name.split()[0]
            try:
                vm_root = _safe_check_output(["/usr/bin/machinectl", "show", "-pRootDirectory", m_uuid])
                if (isinstance(vm_root, bytes)):
                    vm_root = vm_root.decode("utf-8")
            except subprocess.CalledProcessError:
                continue
            vm_root = '='.join(vm_root.rstrip().split('=')[1:])
            if vm_root == chroot_path:
                return m_uuid


@traceLog()
def orphansKill(rootToKill):
    """kill off anything that is still chrooted."""
    getLog().debug("kill orphans")
    if USE_NSPAWN is False:
        for killsig in [signal.SIGTERM, signal.SIGKILL]:
            for fn in [d for d in os.listdir("/proc") if d.isdigit()]:
                try:
                    root = os.readlink("/proc/%s/root" % fn)
                    if os.path.realpath(root) == os.path.realpath(rootToKill):
                        getLog().warning("Process ID %s still running in chroot. Killing with %s...", fn, killsig)
                        pid = int(fn, 10)
                        os.kill(pid, killsig)
                        os.waitpid(pid, 0)
                except OSError:
                    pass
    else:
        m_uuid = get_machinectl_uuid(rootToKill)
        if m_uuid:
            getLog().warning("Machine %s still running. Killing...", m_uuid)
            os.system("/usr/bin/machinectl terminate %s" % m_uuid)


@traceLog()
def yieldSrpmHeaders(srpms, plainRpmOk=0):
    import rpm
    ts = rpm.TransactionSet('/')
    # When RPM > 4.14.90 is common we can use RPMVSF_MASK_NOSIGNATURES, RPMVSF_MASK_NODIGESTS
    # pylint: disable=protected-access
    flags = (rpm._RPMVSF_NOSIGNATURES | rpm._RPMVSF_NODIGESTS)
    ts.setVSFlags(flags)
    for srpm in srpms:
        try:
            fd = os.open(srpm, os.O_RDONLY)
        except OSError as e:
            raise exception.Error("Cannot find/open srpm: %s. Error: %s"
                                  % (srpm, e))
        try:
            hdr = ts.hdrFromFdno(fd)
        except rpm.error as e:
            raise exception.Error(
                "Cannot find/open srpm: %s. Error: %s" % (srpm, e))
        finally:
            os.close(fd)

        if not plainRpmOk and hdr[rpm.RPMTAG_SOURCEPACKAGE] != 1:
            raise exception.Error("File is not an srpm: %s." % srpm)

        yield hdr


@traceLog()
def checkSrpmHeaders(srpms, plainRpmOk=0):
    for dummy in yieldSrpmHeaders(srpms, plainRpmOk):
        pass


@traceLog()
def getNEVRA(hdr):
    import rpm
    name = hdr[rpm.RPMTAG_NAME]
    ver = hdr[rpm.RPMTAG_VERSION]
    rel = hdr[rpm.RPMTAG_RELEASE]
    epoch = hdr[rpm.RPMTAG_EPOCH]
    arch = hdr[rpm.RPMTAG_ARCH]
    if epoch is None:
        epoch = 0
    ret = (name, epoch, ver, rel, arch)
    return tuple(x.decode() if i != 1 else x for i, x in enumerate(ret))


@traceLog()
def cmpKernelVer(str1, str2):
    'compare two kernel version strings and return -1, 0, 1 for less, equal, greater'
    import rpm
    return rpm.labelCompare(('', str1, ''), ('', str2, ''))


@traceLog()
def getAddtlReqs(hdr, conf):
    # Add the 'more_buildreqs' for this SRPM (if defined in config file)
    # pylint: disable=unused-variable
    (name, epoch, ver, rel, arch) = getNEVRA(hdr)
    reqlist = []
    for this_srpm in ['-'.join([name, ver, rel]),
                      '-'.join([name, ver]),
                      '-'.join([name])]:
        if this_srpm in conf:
            more_reqs = conf[this_srpm]
            if isinstance(more_reqs, basestring):
                reqlist.append(more_reqs)
            else:
                reqlist.extend(more_reqs)
            break

    return set(reqlist)


@traceLog()
def unshare(flags):
    getLog().debug("Unsharing. Flags: %s", flags)
    try:
        res = _libc.unshare(flags)
        if res:
            raise exception.UnshareFailed(os.strerror(ctypes.get_errno()))
    except AttributeError:
        pass


def sethostname(hostname):
    getLog().info("Setting hostname: %s", hostname)
    hostname = hostname.encode('utf-8')
    if _libc.sethostname(hostname, len(hostname)) != 0:
        raise OSError('Failed to sethostname %s' % hostname)


# these are called in child process, so no logging
def condChroot(chrootPath):
    if chrootPath is not None:
        saved = {"ruid": os.getuid(), "euid": os.geteuid()}
        setresuid(0, 0, 0)
        os.chdir(chrootPath)
        os.chroot(chrootPath)
        setresuid(saved['ruid'], saved['euid'])


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
        raise OSError(ctypes.get_errno(), os.strerror(ctypes.get_errno()))


def condEnvironment(env=None):
    if not env:
        return
    os.environ.clear()
    for k in list(env.keys()):
        os.putenv(k, env[k])


def condUnshareIPC(unshare_ipc=True):
    if unshare_ipc:
        try:
            unshare(CLONE_NEWIPC)
        except exception.UnshareFailed:
            # IPC and UTS ns are supported since the same kernel version. If this
            # fails, there had to be a warning already
            pass


def condUnshareNet(unshare_net=True):
    if USE_NSPAWN and unshare_net:
        try:
            unshare(CLONE_NEWNET)
            # Set up loopback interface and add default route via loopback in the namespace.
            # Missing default route may confuse some software, see
            # https://github.com/rpm-software-management/mock/issues/113
            ipr = IPRoute()
            dev = ipr.link_lookup(ifname='lo')[0]

            ipr.link('set', index=dev, state='up')
            ipr.route("add", dst="default", gateway="127.0.0.1")
        except exception.UnshareFailed:
            # IPC and UTS ns are supported since the same kernel version. If this
            # fails, there had to be a warning already
            pass
        except Exception as e: # pylint: disable=broad-except
            getLog().warning("network namespace setup failed: %s", e)


def process_input(line):
    out = []
    for char in line.rstrip('\r'):
        if char == '\r':
            out = []
        elif char == '\b':
            out.pop()
        else:
            out.append(char)
    return ''.join(out)


def logOutput(fdout, fderr, logger, returnOutput=1, start=0, timeout=0, printOutput=False,
              child=None, chrootPath=None, pty=False):
    output = ""
    done = False
    fds = [fdout, fderr]

    # set all fds to nonblocking
    for fd in fds:
        flags = fcntl.fcntl(fd, fcntl.F_GETFL)
        if not fd.closed:
            fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

    mockbuild_logger = logging.getLogger('mockbuild')
    stored_propagate = mockbuild_logger.propagate
    if printOutput:
        # prevent output being printed twice when log propagates to stdout
        mockbuild_logger.propagate = 0
        sys.stdout.flush()
    try:
        tail = ""
        ansi_escape = re.compile(r'\x1b\[([0-9]{1,2}(;[0-9]{1,2})?)?[m|K]\x0f?')
        while not done:
            if (time.time() - start) > timeout and timeout != 0:
                done = True
                break

            i_rdy, o_rdy, e_rdy = select.select(fds, [], [], 1)

            if not i_rdy and not o_rdy and not e_rdy:
                if child and child.poll() is not None:
                    logger.info("Child pid '%s' is dead", child.pid)
                    done = True
                    if chrootPath:
                        logger.info("Child dead, killing orphans")
                        orphansKill(chrootPath)
                    continue

            for s in i_rdy:
                # slurp as much input as is ready
                raw = s.read()
                if not raw:
                    done = True
                    break
                if printOutput:
                    if hasattr(sys.stdout, 'buffer'):
                        # python3 would print binary strings ugly
                        # pylint: disable=no-member
                        sys.stdout.buffer.write(raw)
                    else:
                        print(raw, end='')
                    sys.stdout.flush()
                txt_input = raw.decode(encoding, 'replace')
                lines = txt_input.split("\n")
                if tail:
                    lines[0] = tail + lines[0]
                # we may not have all of the last line
                tail = lines.pop()
                if not lines:
                    continue
                if pty:
                    lines = [process_input(line) for line in lines]
                processed_input = '\n'.join(lines) + '\n'
                if logger is not None:
                    for line in lines:
                        if line != '':
                            line = ansi_escape.sub('', line)
                            if fderr is s and not line.startswith('+ '):
                                logger.debug("BUILDSTDERR: %s", line)
                            else:
                                logger.debug(line)
                    for h in logger.handlers:
                        h.flush()
                if returnOutput:
                    output += processed_input

        if tail:
            if pty:
                tail = process_input(tail) + '\n'
            if logger is not None:
                logger.debug(tail)
            if returnOutput:
                output += tail
    finally:
        mockbuild_logger.propagate = stored_propagate

    return output


@traceLog()
def selinuxEnabled():
    """Check if SELinux is enabled (enforcing or permissive)."""
    with open("/proc/mounts") as f:
        for mount in f.readlines():
            (fstype, mountpoint, _) = mount.split(None, 2)
            if fstype == "selinuxfs":
                selinux_mountpoint = mountpoint
                break
        else:
            selinux_mountpoint = "/selinux"

    try:
        enforce_filename = os.path.join(selinux_mountpoint, "enforce")
        with open(enforce_filename) as f:
            if f.read().strip() in ("1", "0"):
                return True
    # pylint: disable=bare-except
    except:
        pass
    return False


def resize_pty(pty):
    try:
        winsize = struct.pack('HHHH', 0, 0, 0, 0)
        winsize = fcntl.ioctl(sys.stdout.fileno(), termios.TIOCGWINSZ, winsize)
        fcntl.ioctl(pty, termios.TIOCSWINSZ, winsize)
    except IOError:
        # Nice to have, but not necessary
        pass


def do(*args, **kargs):
    """ returns output of the command. Arguments are the same as for do_with_status() """
    return do_with_status(*args, **kargs)[0]

# logger =
# output = [1|0]
# chrootPath
#
# The "Not-as-complicated" version
#
@traceLog()
# pylint: disable=unused-argument
def do_with_status(command, shell=False, chrootPath=None, cwd=None, timeout=0, raiseExc=True,
                   returnOutput=0, uid=None, gid=None, user=None, personality=None,
                   printOutput=False, env=None, pty=False, nspawn_args=None, unshare_net=False,
                   *_, **kargs):

    logger = kargs.get("logger", getLog())
    if timeout == 0:
        timeout = _OPS_TIMEOUT
    output = ""
    start = time.time()
    if pty:
        master_pty, slave_pty = os.openpty()
        resize_pty(slave_pty)
        reader = os.fdopen(master_pty, 'rb')
    preexec = ChildPreExec(personality, chrootPath, cwd, uid, gid,
                           unshare_ipc=bool(chrootPath), unshare_net=unshare_net)
    if env is None:
        env = clean_env()
    stdout = None
    try:
        child = None
        if shell and isinstance(command, list):
            command = ['/bin/sh', '-c'] + command
            shell = False
        if chrootPath and USE_NSPAWN:
            logger.debug("Using nspawn with args %s", nspawn_args)
            command = _prepare_nspawn_command(chrootPath, user, command,
                                              nspawn_args=nspawn_args, env=env, cwd=cwd)
        logger.debug("Executing command: %s with env %s and shell %s", command, env, shell)
        with open(os.devnull, "r") as stdin:
            child = subprocess.Popen(
                command,
                shell=shell,
                env=env,
                bufsize=0, close_fds=True,
                stdin=stdin,
                stdout=slave_pty if pty else subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=preexec,
            )
            if not pty:
                stdout = child.stdout
            with child.stderr:
                # use select() to poll for output so we dont block
                output = logOutput(
                    reader if pty else child.stdout, child.stderr,
                    logger, returnOutput, start, timeout, pty=pty,
                    printOutput=printOutput, child=child,
                    chrootPath=chrootPath)
    except:
        # kill children if they arent done
        if child is not None and child.returncode is None:
            os.killpg(child.pid, 9)
        try:
            if child is not None:
                os.waitpid(child.pid, 0)
        except: # pylint: disable=bare-except
            pass
        raise
    finally:
        if pty:
            os.close(slave_pty)
            reader.close()
        if stdout:
            stdout.close()

    # wait until child is done, kill it if it passes timeout
    niceExit = 1
    while child.poll() is None:
        if (time.time() - start) > timeout and timeout != 0:
            niceExit = 0
            os.killpg(child.pid, 15)
        if (time.time() - start) > (timeout + 1) and timeout != 0:
            niceExit = 0
            os.killpg(child.pid, 9)

    # only logging from this point, convert command to string
    if isinstance(command, list):
        command = ' '.join(command)

    if not niceExit:
        raise commandTimeoutExpired("Timeout(%s) expired for command:\n # %s\n%s" % (timeout, command, output))

    logger.debug("Child return code was: %s", child.returncode)
    if raiseExc and child.returncode:
        raise exception.Error("Command failed: \n # %s\n%s" % (command, output), child.returncode)

    return (output, child.returncode)


class ChildPreExec(object):
    def __init__(self, personality, chrootPath, cwd, uid, gid, env=None,
                 shell=False, unshare_ipc=False, unshare_net=False):
        self.personality = personality
        self.chrootPath = chrootPath
        self.cwd = cwd
        self.uid = uid
        self.gid = gid
        self.env = env
        self.shell = shell
        self.unshare_ipc = unshare_ipc
        self.unshare_net = unshare_net
        getLog().debug("child environment: %s", env)

    def __call__(self, *args, **kargs):
        if not self.shell:
            os.setsid()
        os.umask(0o02)
        condUnshareNet(self.unshare_net)
        condPersonality(self.personality)
        condEnvironment(self.env)
        # Even if nspawn is allowed to be used, it won't be used unless there
        # is a chrootPath set
        if not USE_NSPAWN or not self.chrootPath:
            condChroot(self.chrootPath)
            condDropPrivs(self.uid, self.gid)
            condChdir(self.cwd)
        condUnshareIPC(self.unshare_ipc)
        reset_sigpipe()


def reset_sigpipe():
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)


def is_in_dir(path, directory):
    """Tests whether `path` is inside `directory`."""
    # use realpath to expand symlinks
    path = os.path.realpath(path)
    directory = os.path.realpath(directory)

    return os.path.commonprefix([path, directory]) == directory


def _nspawnTempResolvAtExit(path):
    """Remove nspawn temporary resolv.conf from host."""
    try:
        os.remove(path)
    except OSError as e:
        if e.errno not in [errno.ENOENT, errno.EPERM]:
            getLog().warning("unable to delete temporary resolv.conf (%s): %s", path, e)


def _prepare_nspawn_command(chrootPath, user, cmd, nspawn_args=None, env=None, cwd=None):
    cmd_is_list = isinstance(cmd, list)
    if nspawn_args is None:
        nspawn_args = []
    if user:
        # user can be either id or name
        if cmd_is_list:
            cmd = ['-u', str(user)] + cmd
        else:
            raise exception.Error('Internal Error: command must be list or shell=True.')
    elif not cmd_is_list:
        cmd = [cmd]
    nspawn_argv = ['/usr/bin/systemd-nspawn', '-q', '-M', uuid.uuid4().hex, '-D', chrootPath]
    distro_label = distro.linux_distribution(full_distribution_name=False)[0]
    distro_version = float(distro.version() or 0)
    if distro_label not in RHEL_CLONES or distro_version >= 7.5:
        # EL < 7.5 does not support the nspawn -a option. See BZ 1417387
        nspawn_argv += ['-a']
    nspawn_argv.extend(nspawn_args)
    if cwd:
        nspawn_argv.append('--chdir={0}'.format(cwd))
    if env:
        for k, v in env.items():
            nspawn_argv.append('--setenv={0}={1}'.format(k, v))
    cmd = nspawn_argv + cmd
    if cmd_is_list:
        return cmd
    else:
        return " ".join(cmd)


def doshell(chrootPath=None, environ=None, uid=None, gid=None, cmd=None,
            nspawn_args=None,
            unshare_ipc=True,
            unshare_net=False):
    log = getLog()
    log.debug("doshell: chrootPath:%s, uid:%d, gid:%d", chrootPath, uid, gid)
    if environ is None:
        environ = clean_env()
    if 'PROMPT_COMMAND' not in environ:
        environ['PROMPT_COMMAND'] = r'printf "\033]0;<mock-chroot>\007"'
    if 'PS1' not in environ:
        environ['PS1'] = r'<mock-chroot> \s-\v\$ '
    if 'SHELL' not in environ:
        environ['SHELL'] = '/bin/sh'
    log.debug("doshell environment: %s", environ)
    if cmd:
        if not isinstance(cmd, list):
            cmd = [cmd]
        cmd = ['/bin/sh', '-c'] + cmd
    else:
        cmd = ["/bin/sh", "-i", "-l"]
    if USE_NSPAWN:
        # nspawn cannot set gid
        logger.debug("Using nspawn with args %s", nspawn_args)
        cmd = _prepare_nspawn_command(chrootPath, uid, cmd, nspawn_args=nspawn_args, env=environ)
    preexec = ChildPreExec(personality=None, chrootPath=chrootPath, cwd=None,
                           uid=uid, gid=gid, env=environ, shell=True,
                           unshare_ipc=unshare_ipc, unshare_net=unshare_net)
    log.debug("doshell: command: %s", cmd)
    return subprocess.call(cmd, preexec_fn=preexec, env=environ, shell=False)


def run(cmd, isShell=True):
    log = getLog()
    log.debug("run: cmd = %s\n", cmd)
    return subprocess.call(cmd, shell=isShell)


def clean_env():
    env = {
        'TERM': 'vt100',
        'SHELL': '/bin/sh',
        'HOME': '/builddir',
        'HOSTNAME': 'mock',
        'PATH': '/usr/bin:/bin:/usr/sbin:/sbin',
    }
    env['LANG'] = os.environ.setdefault('LANG', 'C.UTF-8')
    return env


def get_fs_type(path):
    cmd = ['/usr/bin/stat', '-f', '-L', '-c', '%T', path]
    p = subprocess.Popen(cmd, shell=False, stdout=subprocess.PIPE,
                         universal_newlines=True)
    p.wait()
    with p.stdout as f:
        return f.readline().strip()


def find_non_nfs_dir():
    dirs = ('/dev/shm', '/run', '/tmp', '/usr/tmp', '/')
    for d in dirs:
        if not get_fs_type(d).startswith('nfs'):
            return d
    raise exception.Error('Cannot find non-NFS directory in: %s' % dirs)


@traceLog()
def setup_default_config_opts(unprivUid, version, pkgpythondir):
    "sets up default configuration."
    config_opts = TemplatedDictionary()
    config_opts['version'] = version
    config_opts['basedir'] = '/var/lib/mock'  # root name is automatically added to this
    config_opts['resultdir'] = '%(basedir)s/%(root)s/result'
    config_opts['cache_topdir'] = '/var/cache/mock'
    config_opts['clean'] = True
    config_opts['check'] = True
    config_opts['post_install'] = False
    config_opts['chroothome'] = '/builddir'
    config_opts['log_config_file'] = 'logging.ini'
    config_opts['rpmbuild_timeout'] = 0
    config_opts['chrootuid'] = unprivUid
    try:
        config_opts['chrootgid'] = grp.getgrnam("mock")[2]
    except KeyError:
        #  'mock' group doesn't exist, must set in config file
        pass
    config_opts['chrootgroup'] = 'mock'
    config_opts['chrootuser'] = 'mockbuild'
    config_opts['build_log_fmt_name'] = "unadorned"
    config_opts['root_log_fmt_name'] = "detailed"
    config_opts['state_log_fmt_name'] = "state"
    config_opts['online'] = True
    config_opts['use_nspawn'] = True
    config_opts['rpmbuild_networking'] = False
    config_opts['nspawn_args'] = ['--capability=cap_ipc_lock']
    config_opts['use_container_host_hostname'] = True
    config_opts['use_bootstrap_container'] = False

    config_opts['internal_dev_setup'] = True

    # cleanup_on_* only take effect for separate --resultdir
    # config_opts provides fine-grained control. cmdline only has big hammer
    config_opts['cleanup_on_success'] = True
    config_opts['cleanup_on_failure'] = True

    config_opts['exclude_from_homedir_cleanup'] = ['build/SOURCES', '.bash_history',
                                                   '.bashrc']

    config_opts['createrepo_on_rpms'] = False
    config_opts['createrepo_command'] = '/usr/bin/createrepo_c -d -q -x *.src.rpm'  # default command

    config_opts['tar'] = "gnutar"

    config_opts['backup_on_clean'] = False
    config_opts['backup_base_dir'] = os.path.join(config_opts['basedir'], "backup")

    # (global) plugins and plugin configs.
    # ordering constraings: tmpfs must be first.
    #    root_cache next.
    #    after that, any plugins that must create dirs (yum_cache)
    #    any plugins without preinit hooks should be last.
    config_opts['plugins'] = PLUGIN_LIST
    config_opts['plugin_dir'] = os.path.join(pkgpythondir, "plugins")
    config_opts['plugin_conf'] = {
        'ccache_enable': False,
        'ccache_opts': {
            'max_cache_size': "4G",
            'compress': None,
            'dir': "%(cache_topdir)s/%(root)s/ccache/u%(chrootuid)s/"},
        'yum_cache_enable': True,
        'yum_cache_opts': {
            'max_age_days': 30,
            'max_metadata_age_days': 30,
            'dir': "%(cache_topdir)s/%(root)s/%(package_manager)s_cache/",
            'target_dir': "/var/cache/%(package_manager)s/",
            'online': True},
        'root_cache_enable': True,
        'root_cache_opts': {
            'age_check': True,
            'max_age_days': 15,
            'dir': "%(cache_topdir)s/%(root)s/root_cache/",
            'tar': "gnutar",
            'compress_program': 'pigz',
            'decompress_program': None,
            'exclude_dirs': ["./proc", "./sys", "./dev", "./tmp/ccache", "./var/cache/yum", "./var/cache/dnf"],
            'extension': '.gz'},
        'bind_mount_enable': True,
        'bind_mount_opts': {
            'dirs': [
                # specify like this:
                # ('/host/path', '/bind/mount/path/in/chroot/' ),
                # ('/another/host/path', '/another/bind/mount/path/in/chroot/'),
            ],
            'create_dirs': False},
        'mount_enable': True,
        'mount_opts': {'dirs': [
            # specify like this:
            # ("/dev/device", "/mount/path/in/chroot/", "vfstype", "mount_options"),
        ]},
        'tmpfs_enable': False,
        'tmpfs_opts': {
            'required_ram_mb': 900,
            'max_fs_size': None,
            'mode': '0755',
            'keep_mounted': False},
        'selinux_enable': True,
        'selinux_opts': {},
        'package_state_enable': True,
        'package_state_opts': {
            'available_pkgs': False,
            'installed_pkgs': True,
        },
        'pm_request_enable': False,
        'pm_request_opts': {},
        'lvm_root_enable': False,
        'lvm_root_opts': {
            'pool_name': 'mockbuild',
        },
        'chroot_scan_enable': False,
        'chroot_scan_opts': {
            'regexes': [
                "^[^k]?core(\\.\\d+)?$", "\\.log$",
            ],
            'only_failed': True},
        'sign_enable': False,
        'sign_opts': {
            'cmd': 'rpmsign',
            'opts': '--addsign %(rpms)s',
        },
        'hw_info_enable': True,
        'hw_info_opts': {
        },
    }

    config_opts['environment'] = {
        'TERM': 'vt100',
        'SHELL': '/bin/bash',
        'HOME': '/builddir',
        'HOSTNAME': 'mock',
        'PATH': '/usr/bin:/bin:/usr/sbin:/sbin',
        'PROMPT_COMMAND': r'printf "\033]0;<mock-chroot>\007"',
        'PS1': r'<mock-chroot> \s-\v\$ ',
        'LANG': os.environ.setdefault('LANG', 'C.UTF-8'),
    }

    runtime_plugins = [runtime_plugin
                       for (runtime_plugin, _)
                       in [os.path.splitext(os.path.basename(tmp_path))
                           for tmp_path
                           in glob(config_opts['plugin_dir'] + "/*.py")]
                       if runtime_plugin not in config_opts['plugins']]
    for runtime_plugin in sorted(runtime_plugins):
        config_opts['plugins'].append(runtime_plugin)
        config_opts['plugin_conf'][runtime_plugin + "_enable"] = False
        config_opts['plugin_conf'][runtime_plugin + "_opts"] = {}

    # SCM defaults
    config_opts['scm'] = False
    config_opts['scm_opts'] = {
        'method': 'git',
        'cvs_get': 'cvs -d /srv/cvs co SCM_BRN SCM_PKG',
        'git_get': 'git clone SCM_BRN git://localhost/SCM_PKG.git SCM_PKG',
        'svn_get': 'svn co file:///srv/svn/SCM_PKG/SCM_BRN SCM_PKG',
        'distgit_get': 'rpkg clone -a --branch SCM_BRN SCM_PKG SCM_PKG',
        'distgit_src_get': 'rpkg sources',
        'spec': 'SCM_PKG.spec',
        'ext_src_dir': os.devnull,
        'write_tar': False,
        'git_timestamps': False,
        'exclude_vcs': True,
    }

    # dependent on guest OS
    config_opts['useradd'] = \
        '/usr/sbin/useradd -o -m -u %(uid)s -g %(gid)s -d %(home)s -n %(user)s'
    config_opts['use_host_resolv'] = False
    config_opts['chroot_setup_cmd'] = ('groupinstall', 'buildsys-build')
    config_opts['target_arch'] = 'i386'
    config_opts['releasever'] = None
    config_opts['rpmbuild_arch'] = None  # <-- None means set automatically from target_arch
    config_opts['yum.conf'] = ''
    config_opts['yum_builddep_opts'] = []
    config_opts['yum_common_opts'] = []
    config_opts['update_before_build'] = True
    config_opts['priorities.conf'] = '\n[main]\nenabled=0'
    config_opts['rhnplugin.conf'] = '\n[main]\nenabled=0'
    config_opts['subscription-manager.conf'] = ''
    config_opts['more_buildreqs'] = {}
    config_opts['nosync'] = False
    config_opts['nosync_force'] = False
    config_opts['files'] = {}
    config_opts['macros'] = {
        '%_topdir': '%s/build' % config_opts['chroothome'],
        '%_rpmfilename': '%%{NAME}-%%{VERSION}-%%{RELEASE}.%%{ARCH}.rpm',
    }
    config_opts['hostname'] = None
    config_opts['module_enable'] = []
    config_opts['module_install'] = []
    config_opts['forcearch'] = None

    config_opts['bootstrap_chroot_additional_packages'] = []
    config_opts['bootstrap_module_enable'] = []
    config_opts['bootstrap_module_install'] = []

    # security config
    config_opts['no_root_shells'] = False
    config_opts['extra_chroot_dirs'] = []

    config_opts['package_manager'] = 'yum'

    config_opts['dynamic_buildrequires'] = False

    # configurable commands executables
    config_opts['yum_command'] = '/usr/bin/yum'
    config_opts['system_yum_command'] = '/usr/bin/yum'
    config_opts['yum_install_command'] = 'install yum yum-utils shadow-utils distribution-gpg-keys'
    config_opts['yum_builddep_command'] = '/usr/bin/yum-builddep'
    config_opts['dnf_command'] = '/usr/bin/dnf'
    config_opts['system_dnf_command'] = '/usr/bin/dnf'
    config_opts['dnf_install_command'] = 'install dnf dnf-plugins-core distribution-gpg-keys'
    config_opts['microdnf_command'] = '/usr/bin/microdnf'
    # "dnf-install" is special keyword which tells mock to use install but with DNF
    config_opts['microdnf_install_command'] = 'dnf-install microdnf dnf dnf-plugins-core distribution-gpg-keys'
    config_opts['microdnf_builddep_command'] = '/usr/bin/dnf'
    config_opts['microdnf_builddep_opts'] = []
    config_opts['microdnf_common_opts'] = []
    config_opts['rpm_command'] = '/bin/rpm'
    config_opts['rpmbuild_command'] = '/usr/bin/rpmbuild'

    config_opts['opstimeout'] = 0

    return config_opts


@traceLog()
def set_config_opts_per_cmdline(config_opts, options, args):
    "takes processed cmdline args and sets config options."

    cli_opt_new = {}
    for cli_opt in options.cli_config_opts:
        k, v = cli_opt.split("=", 1)
        # convert string to boolean and int if possible
        if v in ['true', 'True']:
            v = True
        elif v in ['false', 'False']:
            v = False
        elif v in ['none', 'None']:
            v = None
        else:
            try:
                v = int(v)
            except ValueError:
                pass
        if k not in cli_opt_new:
            cli_opt_new[k] = v
        elif isinstance(cli_opt_new[k], list):
            cli_opt_new[k].append(v)
        else:
            if v == '':
                # hack!
                # specify k twice, second v is empty, this make it list with one value
                cli_opt_new[k] = [cli_opt_new[k]]
            else:
                cli_opt_new[k] = [cli_opt_new[k], v]
    config_opts.update(cli_opt_new)

    config_opts['verbose'] = options.verbose
    if 'print_main_output' not in config_opts or config_opts['print_main_output'] is None:
        config_opts['print_main_output'] = config_opts['verbose'] > 0 and sys.stderr.isatty()

    # do some other options and stuff
    if options.arch:
        config_opts['target_arch'] = options.arch
    if options.rpmbuild_arch:
        config_opts['rpmbuild_arch'] = options.rpmbuild_arch
    elif config_opts['rpmbuild_arch'] is None:
        config_opts['rpmbuild_arch'] = config_opts['target_arch']
    if options.forcearch:
        config_opts['forcearch'] = options.forcearch

    if not options.clean:
        config_opts['clean'] = options.clean

    if not options.check:
        config_opts['check'] = options.check

    if options.post_install:
        config_opts['post_install'] = options.post_install

    for option in options.rpmwith:
        options.rpmmacros.append("_with_%s --with-%s" %
                                 (option.replace("-", "_"), option))

    for option in options.rpmwithout:
        options.rpmmacros.append("_without_%s --without-%s" %
                                 (option.replace("-", "_"), option))

    for macro in options.rpmmacros:
        try:
            macro = macro.strip()
            k, v = macro.split(" ", 1)
            if not k.startswith('%'):
                k = '%%%s' % k
            config_opts['macros'].update({k: v})
        except:
            raise exception.BadCmdline(
                "Bad option for '--define' (%s).  Use --define 'macro expr'"
                % macro)

    if options.macrofile:
        config_opts['macrofile'] = os.path.expanduser(options.macrofile)
        if not os.path.isfile(config_opts['macrofile']):
            raise exception.BadCmdline(
                "Input rpm macros file does not exist: %s"
                % options.macrofile)

    if options.resultdir:
        config_opts['resultdir'] = os.path.expanduser(options.resultdir)
    if options.rootdir:
        config_opts['rootdir'] = os.path.expanduser(options.rootdir)
    if options.uniqueext:
        config_opts['unique-ext'] = options.uniqueext
    if options.rpmbuild_timeout is not None:
        config_opts['rpmbuild_timeout'] = options.rpmbuild_timeout
    if options.bootstrapchroot is not None:
        config_opts['use_bootstrap_container'] = options.bootstrapchroot

    for i in options.disabled_plugins:
        if i not in config_opts['plugins']:
            raise exception.BadCmdline(
                "Bad option for '--disable-plugin=%s'. Expecting one of: %s"
                % (i, config_opts['plugins']))
        config_opts['plugin_conf']['%s_enable' % i] = False
    for i in options.enabled_plugins:
        if i not in config_opts['plugins']:
            raise exception.BadCmdline(
                "Bad option for '--enable-plugin=%s'. Expecting one of: %s"
                % (i, config_opts['plugins']))
        config_opts['plugin_conf']['%s_enable' % i] = True
    for option in options.plugin_opts:
        try:
            p, kv = option.split(":", 1)
            k, v = kv.split("=", 1)
        except:
            raise exception.BadCmdline(
                "Bad option for '--plugin-option' (%s).  Use --plugin-option 'plugin:key=value'"
                % option)
        if p not in config_opts['plugins']:
            raise exception.BadCmdline(
                "Bad option for '--plugin-option' (%s).  No such plugin: %s"
                % (option, p))
        try:
            v = literal_eval(v)
        except: # pylint: disable=bare-except
            pass
        config_opts['plugin_conf'][p + "_opts"].update({k: v})

    global USE_NSPAWN
    USE_NSPAWN = config_opts['use_nspawn']
    if options.old_chroot:
        USE_NSPAWN = False
    if options.new_chroot:
        USE_NSPAWN = True

    if options.enable_network:
        config_opts['rpmbuild_networking'] = True
        config_opts['use_host_resolv'] = True

    if options.mode in ("rebuild",) and len(args) > 1 and not options.resultdir:
        raise exception.BadCmdline(
            "Must specify --resultdir when building multiple RPMS.")

    if options.cleanup_after is False:
        config_opts['cleanup_on_success'] = False
        config_opts['cleanup_on_failure'] = False

    if options.cleanup_after is True:
        config_opts['cleanup_on_success'] = True
        config_opts['cleanup_on_failure'] = True

    check_config(config_opts)
    # can't cleanup unless resultdir is separate from the root dir
    rootdir = os.path.join(config_opts['basedir'], config_opts['root'])
    if is_in_dir(config_opts['resultdir'] % config_opts, rootdir):
        config_opts['cleanup_on_success'] = False
        config_opts['cleanup_on_failure'] = False

    config_opts['cache_alterations'] = options.cache_alterations

    config_opts['online'] = options.online

    if options.pkg_manager:
        config_opts['package_manager'] = options.pkg_manager
    if options.mode == 'yum-cmd':
        config_opts['package_manager'] = 'yum'
    if options.mode == 'dnf-cmd':
        config_opts['package_manager'] = 'dnf'

    if options.short_circuit:
        config_opts['short_circuit'] = options.short_circuit
        config_opts['clean'] = False

    if options.rpmbuild_opts:
        config_opts['rpmbuild_opts'] = options.rpmbuild_opts

    config_opts['enable_disable_repos'] = options.enable_disable_repos

    if options.scm:
        try:
            # pylint: disable=unused-variable
            from . import scm
        except ImportError as e:
            raise exception.BadCmdline(
                "Mock SCM module not installed: %s" % e)

        config_opts['scm'] = options.scm
        for option in options.scm_opts:
            try:
                k, v = option.split("=", 1)
                config_opts['scm_opts'].update({k: v})
            except:
                raise exception.BadCmdline(
                    "Bad option for '--scm-option' (%s).  Use --scm-option 'key=value'"
                    % option)


def check_config(config_opts):
    if 'root' not in config_opts:
        raise exception.ConfigError("Error in configuration "
                                    "- option config_opts['root'] must be present in your config.")


@traceLog()
def include(config_file, config_opts, is_statement=False):
    if os.path.exists(config_file):
        if is_statement and config_file in config_opts['config_paths']:
            getLog().warning("Multiple inclusion of %s, skipping" % config_file)
            return

        config_opts['config_paths'].append(config_file)

        with open(config_file) as f:
            content = f.read()
            content = re.sub(r'include\((.*)\)', r'include(\g<1>, config_opts, True)', content)
            code = compile(content, config_file, 'exec')
        # pylint: disable=exec-used
        exec(code)
    else:
        raise exception.ConfigError("Could not find included config file: %s" % config_file)


@traceLog()
def update_config_from_file(config_opts, config_file, uid_manager):
    config_file = os.path.realpath(config_file)
    r_pipe, w_pipe = os.pipe()
    if os.fork() == 0:
        try:
            os.close(r_pipe)
            if uid_manager and not all(getresuid()):
                uid_manager.dropPrivsForever()
            include(config_file, config_opts)
            with os.fdopen(w_pipe, 'wb') as writer:
                pickle.dump(config_opts, writer)
        except: # pylint: disable=bare-except
            import traceback
            etype, evalue, raw_tb = sys.exc_info()
            tb = traceback.extract_tb(raw_tb)
            tb = [entry for entry in tb if entry[0] == config_file]
            print('\n'.join(traceback.format_list(tb)), file=sys.stderr)
            print('\n'.join(traceback.format_exception_only(etype, evalue)),
                  file=sys.stderr)
            sys.exit(1)
        sys.exit(0)
    else:
        os.close(w_pipe)
        with os.fdopen(r_pipe, 'rb') as reader:
            while True:
                try:
                    new_config = reader.read()
                    break
                except OSError as e:
                    if e.errno != errno.EINTR:
                        raise
            _, ret = os.wait()
            if ret != 0:
                raise exception.ConfigError('Error in configuration')
            if new_config:
                config_opts.update(pickle.loads(new_config))


def setup_operations_timeout(config_opts):
    global _OPS_TIMEOUT
    _OPS_TIMEOUT = config_opts.get('opstimeout', 0)


@traceLog()
def do_update_config(log, config_opts, cfg, uidManager, name, skipError=True):
    if os.path.exists(cfg):
        config_opts['config_paths'].append(cfg)
        update_config_from_file(config_opts, cfg, uidManager)
        setup_operations_timeout(config_opts)
        check_macro_definition(config_opts)
    elif not skipError:
        log.error("Could not find required config file: %s", cfg)
        if name == "default":
            log.error("  Did you forget to specify the chroot to use with '-r'?")
        if "/" in cfg:
            log.error("  If you're trying to specify a path, include the .cfg extension, e.g. -r ./target.cfg")
        sys.exit(1)

@traceLog()
def setup_host_resolv(config_opts):
    if not config_opts['use_host_resolv']:
        # default /etc/hosts contents
        if 'etc/hosts' not in config_opts['files']:
            config_opts['files']['etc/hosts'] = dedent('''\
                127.0.0.1 localhost localhost.localdomain
                ::1       localhost localhost.localdomain localhost6 localhost6.localdomain6
                ''')
        # bind mount an empty /etc/resolv.conf when using nspawn and networking is disabled
        if config_opts['use_nspawn'] and not config_opts['rpmbuild_networking']:
            resolv_path = (tempfile.mkstemp(prefix="mock-resolv."))[1]
            atexit.register(_nspawnTempResolvAtExit, resolv_path)
            config_opts['nspawn_args'] += ['--bind={0}:/etc/resolv.conf'.format(resolv_path)]

@traceLog()
def load_config(config_path, name, uidManager, version, pkg_python_dir):
    log = logging.getLogger()
    if uidManager:
        gid = uidManager.unprivUid
    else:
        gid = os.getuid()
    config_opts = setup_default_config_opts(gid, version, pkg_python_dir)

    # array to save config paths
    config_opts['config_paths'] = []
    config_opts['chroot_name'] = name

    # Read in the config files: default, and then user specified
    if name.endswith('.cfg'):
        # If the .cfg is explicitly specified we take the root arg to
        # specify a path, rather than looking it up in the configdir.
        chroot_cfg_path = name
        config_opts['chroot_name'] = os.path.splitext(os.path.basename(name))[0]
    else:
        chroot_cfg_path = '%s/%s.cfg' % (config_path, name)
    config_opts['config_file'] = chroot_cfg_path

    cfg = os.path.join(config_path, 'site-defaults.cfg')
    do_update_config(log, config_opts, cfg, uidManager, name)

    do_update_config(log, config_opts, chroot_cfg_path, uidManager, name, skipError=False)

    # Read user specific config file
    cfg = os.path.join(os.path.expanduser(
        '~' + pwd.getpwuid(os.getuid())[0]), '.mock/user.cfg')
    do_update_config(log, config_opts, cfg, uidManager, name)
    cfg = os.path.join(os.path.expanduser(
        '~' + pwd.getpwuid(os.getuid())[0]), '.config/mock.cfg')
    do_update_config(log, config_opts, cfg, uidManager, name)

    if config_opts['use_container_host_hostname'] and '%_buildhost' not in config_opts['macros']:
        config_opts['macros']['%_buildhost'] = socket.getfqdn()
    return config_opts


@traceLog()
def check_macro_definition(config_opts):
    for k, v in config_opts['macros'].items():
        if not k or (not v and (v is not None)) or len(k.split()) != 1:
            raise exception.BadCmdline(
                "Bad macros 'config_opts['macros']['%s'] = ['%s']'" % (k, v))
        if not k.startswith('%'):
            del config_opts['macros'][k]
            k = '%{0}'.format(k)
            config_opts['macros'].update({k: v})


@traceLog()
def pretty_getcwd():
    try:
        return os.getcwd()
    except OSError:
        if ORIGINAL_CWD is not None:
            return ORIGINAL_CWD
        else:
            return find_non_nfs_dir()


ORIGINAL_CWD = None
ORIGINAL_CWD = pretty_getcwd()


@traceLog()
def find_btrfs_in_chroot(mockdir, chroot_path):
    """
    Find a btrfs subvolume inside the chroot.

    Example btrfs output:
    ID 258 gen 32689 top level 5 path root
    ID 493 gen 32682 top level 258 path var/lib/mock/fedora-rawhide-x86_64/root/var/lib/machines

    The subvolume's path will always be the 9th field of the output and
    will not contain a leading '/'. The output will also contain additional
    newline at the end, which should not be parsed.
    """

    try:
        output = do(["btrfs", "subv", "list", mockdir], returnOutput=1, printOutput=False)
    except OSError as e:
        # btrfs utility does not exist, nothing we can do about it
        if e.errno == errno.ENOENT:
            return None
        raise e
    except Exception as e: # pylint: disable=broad-except
        # it is not btrfs volume
        log = getLog()
        log.debug("Please ignore the error above above about btrfs.")
        return None

    for l in output[:-1].splitlines():
        subv = l.split()[8]
        if subv.startswith(chroot_path[1:]):
            return subv
    return None
