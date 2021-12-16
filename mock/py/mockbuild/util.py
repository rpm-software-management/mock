# -*- coding: utf-8 -*-
# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# License: GPL2 or later see COPYING
# Written by Michael Brown
# Sections by Seth Vidal
# Sections taken from Mach by Thomas Vander Stichele
# Copyright (C) 2007 Michael E Brown <mebrown@michaels-house.net>
from __future__ import print_function

import atexit
import ctypes
import errno
import fcntl
from glob import glob
import logging
import os
import os.path
import pipes
import re
import select
import signal
import shlex
import shutil
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

from mockbuild.mounts import BindMountPoint

from . import exception
from . import file_util
from . import text
from .trace_decorator import getLog, traceLog
from .uid import setresuid
from pyroute2 import IPRoute

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

USE_NSPAWN = False

_NSPAWN_HELP_OUTPUT = None

RHEL_CLONES = ['centos', 'deskos', 'ol', 'rhel', 'scientific']

_OPS_TIMEOUT = 0


def cmd_pretty(cmd):
    if isinstance(cmd, list):
        return ' '.join(pipes.quote(arg) for arg in cmd)
    return cmd


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
    vm_list = _safe_check_output(["/bin/machinectl", "list", "--no-pager"])
    if (isinstance(vm_list, bytes)):
        vm_list = vm_list.decode("utf-8")
    vm_list = '\n'.join(vm_list.split('\n')[1:-2])
    for name in vm_list.split("\n"):
        if len(name) > 0:
            m_uuid = name.split()[0]
            try:
                vm_root = _safe_check_output(["/bin/machinectl", "show", "-pRootDirectory", m_uuid])
                if (isinstance(vm_root, bytes)):
                    vm_root = vm_root.decode("utf-8")
            except subprocess.CalledProcessError:
                continue
            vm_root = '='.join(vm_root.rstrip().split('=')[1:])
            if vm_root == chroot_path:
                return m_uuid
    # we should never get here
    return None


def compare_two_paths_cached(path1, path2, path_cache):
    """ compare two files on dev/ino pairs """
    def file_dev_ino(path):
        """ Return dev/ino pair for path, and cache results """
        if path in path_cache:
            return path_cache[path]
        stat_val = os.stat(os.path.realpath(path))
        ret = path_cache[path] = stat_val.st_dev, stat_val.st_ino
        return ret
    return file_dev_ino(path1) == file_dev_ino(path2)


@traceLog()
def orphansKill(rootToKill, manual_forced=False):
    """
    Kill off anything that is still chrooted.

    When USE_NSPAWN==False, this method manually detects the running processes
    in chroot by reading the /proc file-system.  When USE_NSPAWN==True, it just
    relies on '/bin/machinectl terminate' call.

    When manual_forced==True, the manual kill based on /proc is enforced.
    """
    getLog().debug("kill orphans")
    if USE_NSPAWN is False or manual_forced:
        path_cache = {}
        for killsig in [signal.SIGTERM, signal.SIGKILL]:
            for fn in [d for d in os.listdir("/proc") if d.isdigit()]:
                try:
                    root = os.readlink("/proc/%s/root" % fn)
                    if compare_two_paths_cached(root, rootToKill, path_cache):
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
            os.system("/bin/machinectl terminate %s" % m_uuid)


@traceLog()
def yieldSrpmHeaders(srpms, plainRpmOk=0):
    # pylint: disable=import-outside-toplevel
    import rpm
    ts = rpm.TransactionSet('/')
    # When RPM > 4.14.90 is common we can use RPMVSF_MASK_NOSIGNATURES, RPMVSF_MASK_NODIGESTS
    # pylint: disable=protected-access
    flags = (rpm._RPMVSF_NOSIGNATURES | rpm._RPMVSF_NODIGESTS)
    ts.setVSFlags(flags)
    for srpm in srpms:
        srpm = host_file(srpm)
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
    # pylint: disable=import-outside-toplevel
    import rpm
    name = hdr[rpm.RPMTAG_NAME]
    ver = hdr[rpm.RPMTAG_VERSION]
    rel = hdr[rpm.RPMTAG_RELEASE]
    epoch = hdr[rpm.RPMTAG_EPOCH]
    arch = hdr[rpm.RPMTAG_ARCH]
    if epoch is None:
        epoch = 0
    ret = (name, epoch, ver, rel, arch)
    return tuple(text._to_text(x) if i != 1 else x for i, x in enumerate(ret))


@traceLog()
def cmpKernelVer(str1, str2):
    'compare two kernel version strings and return -1, 0, 1 for less, equal, greater'
    # pylint: disable=import-outside-toplevel
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
            if isinstance(more_reqs, str):
                reqlist.append(more_reqs)
            else:
                reqlist.extend(more_reqs)
            break

    return set(reqlist)


@traceLog()
def unshare(flags):
    #getLog().debug("Unsharing. Flags: %s", flags)
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
              child=None, chrootPath=None, pty=False, returnStderr=True):
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

                if returnStderr is False and s == fderr:
                    continue

                txt_input = raw.decode(text.encoding, 'replace')
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
                if "mock_stderr_line_prefix" in dir(mockbuild_logger):
                    mock_stderr_line_prefix = mockbuild_logger.mock_stderr_line_prefix
                else:
                    mock_stderr_line_prefix = ""
                if logger is not None:
                    for line in lines:
                        if line != '':
                            line = ansi_escape.sub('', line)
                            if fderr is s and not line.startswith('+ '):
                                logger.debug("%s%s", mock_stderr_line_prefix, line)
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
                   returnStderr=True, *_, **kargs):
    logger = kargs.get("logger", getLog())
    if timeout == 0:
        timeout = _OPS_TIMEOUT
    output = ""
    start = time.time()
    if pty:
        lead_pty, sub_pty = os.openpty()
        resize_pty(sub_pty)
        reader = os.fdopen(lead_pty, 'rb')
    preexec = ChildPreExec(personality, chrootPath, cwd, uid, gid,
                           unshare_ipc=bool(chrootPath), unshare_net=unshare_net)
    if env is None:
        env = clean_env()
    stdout = None

    if isinstance(command, list):
        # convert int args to strings
        command = [str(x) for x in command]

    try:
        child = None
        if chrootPath and USE_NSPAWN:
            logger.debug("Using nspawn with args %s", nspawn_args)
            command = _prepare_nspawn_command(chrootPath, user, command,
                                              nspawn_args=nspawn_args,
                                              env=env, cwd=cwd, shell=shell)
            shell = False
        logger.debug("Executing command: %s with env %s and shell %s", command, env, shell)
        with open(os.devnull, "r") as stdin:
            child = subprocess.Popen(
                command,
                shell=shell,
                env=env,
                bufsize=0, close_fds=True,
                stdin=stdin,
                stdout=sub_pty if pty else subprocess.PIPE,
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
                    chrootPath=chrootPath, returnStderr=returnStderr)
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
            os.close(sub_pty)
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
        raise exception.commandTimeoutExpired("Timeout(%s) expired for command:\n # %s\n%s" %
                                              (timeout, command, output))

    logger.debug("Child return code was: %s", child.returncode)
    if raiseExc and child.returncode:
        raise exception.Error("Command failed: \n # %s\n%s" % (command, output), child.returncode)

    return (output, child.returncode)


class ChildPreExec(object):
    def __init__(self, personality, chrootPath, cwd, uid, gid, env=None,
                 shell=False, unshare_ipc=False, unshare_net=False,
                 no_setsid=False):
        """
        Params:
        - no_setsid - assure we don't call os.setsid(), as the process we run
            calls that itself
        """
        self.personality = personality
        self.chrootPath = chrootPath
        self.cwd = cwd
        self.uid = uid
        self.gid = gid
        self.env = env
        self.shell = shell
        self.unshare_ipc = unshare_ipc
        self.unshare_net = unshare_net
        self.no_setsid = no_setsid
        getLog().debug("child environment: %s", env)

    def __call__(self, *args, **kargs):
        if not self.shell and not self.no_setsid:
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


def setup_operations_timeout(config_opts):
    global _OPS_TIMEOUT
    _OPS_TIMEOUT = config_opts.get('opstimeout', 0)


def set_use_nspawn(value):
    global USE_NSPAWN
    USE_NSPAWN = value


class BindMountedFile(str):
    'see host_file() doc'
    def __new__(cls, value, on_host=None):
        the_string = str.__new__(cls, value)
        the_string.on_host = on_host if on_host else value
        return the_string


def host_file(file):
    """
    Some functions accept arguments which may be either str() or
    BindMountedFile();  we use this helper to work with those transparently.
    TODO: all the code parts which need this should be fixed so they
    are executed _inside_ bootstrap chroot, not on host.
    """
    return file.on_host if hasattr(file, 'on_host') else file


def reset_sigpipe():
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)


def _nspawnTempResolvAtExit(path):
    """Remove nspawn temporary resolv.conf from host."""
    try:
        os.remove(path)
    except OSError as e:
        if e.errno not in [errno.ENOENT, errno.EPERM]:
            getLog().warning("unable to delete temporary resolv.conf (%s): %s", path, e)


def systemd_nspawn_help_output():
    """ Get (cached, so we don't re-run) systemd-nspawn --help output. """
    global _NSPAWN_HELP_OUTPUT  # pylint: disable=global-statement
    if _NSPAWN_HELP_OUTPUT is not None:
        return _NSPAWN_HELP_OUTPUT

    _NSPAWN_HELP_OUTPUT = subprocess.check_output(
        'systemd-nspawn --help || true',
        shell=True)
    _NSPAWN_HELP_OUTPUT = _NSPAWN_HELP_OUTPUT.decode('utf-8', errors='ignore')
    return _NSPAWN_HELP_OUTPUT


def _check_nspawn_pipe_option():
    """
    Detect whether host's systemd-nspawn supports --pipe argument and if we can
    use it for non-interactive commands.  Before --pipe was implemented in
    nspawn the default behavior was to detect tty => and use 'interactive' vs.
    'pipe'.  Later the default was changed to 'interactive' vs. 'read-only'
    (systemd commit de40a3037).
    """
    output = systemd_nspawn_help_output()
    return '--pipe' in output and '--console' in output


def _check_nspawn_resolv_conf():
    """
    Detect that --resolv-conf= option is supported in systemd-nspawn, and if
    yes - switch the default value 'auto' to 'off' so nspawn doesn't override
    our pre-generated resolv.conf file.
    """
    return '--resolv-conf' in systemd_nspawn_help_output()


def check_nspawn_has_chdir_option():
    """
    Older systemd-nspawn versions don't have --chdir option, and sometimes we
    need to know we work with such version.
    """
    return '--chdir' in systemd_nspawn_help_output()


def _prepare_nspawn_command(chrootPath, user, cmd, nspawn_args=None, env=None,
                            cwd=None, interactive=False, shell=False):
    nspawn_argv = ['/usr/bin/systemd-nspawn', '-q', '-M', uuid.uuid4().hex, '-D', chrootPath]
    distro_label = distro.id()
    try:
        distro_version = float(distro.version() or 0)
    except ValueError:
        distro_version = 0
    if distro_label not in RHEL_CLONES or distro_version >= 7.5:
        # EL < 7.5 does not support the nspawn -a option. See BZ 1417387
        nspawn_argv += ['-a']

    if user:
        # user can be either id or name
        nspawn_argv += ['-u', str(user)]

    if nspawn_args:
        nspawn_argv.extend(nspawn_args)

    if _check_nspawn_pipe_option():
        if not interactive or not (sys.stdin.isatty() and sys.stdout.isatty()):
            nspawn_argv += ['--console=pipe']

    if cwd:
        nspawn_argv.append('--chdir={0}'.format(cwd))

    assert env is not None

    # Those variables are expected to be set _inside_ the container
    for k, v in env.items():
        nspawn_argv.append('--setenv={0}={1}'.format(k, v))

    # And these need to be set outside the container (processed by nspawn)
    env['SYSTEMD_NSPAWN_TMPFS_TMP'] = '0'
    env['SYSTEMD_SECCOMP'] = '0'

    if _check_nspawn_resolv_conf():
        nspawn_argv.append("--resolv-conf=off")

    # The '/bin/sh -c' wrapper is explicitly requested (--shell).  In this case
    # we shrink the list of arguments into one shell command, so the command is
    # completely shell-expanded.
    if shell and isinstance(cmd, list):
        cmd = ' '.join(cmd)

    # HACK!  No matter if --shell/--chroot is used, we have documented that we
    # shell-expand the CMD if there are no ARGS.  This is historical
    # requirement that other people probably depend on.
    if isinstance(cmd, str):
        cmd = ['/bin/sh', '-c', cmd]

    return nspawn_argv + cmd

def doshell(chrootPath=None, environ=None, uid=None, gid=None, cmd=None,
            cwd=None,
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

    no_setsid = False
    shell = True
    if not cmd:
        cmd = ["/bin/sh", "-i", "-l"]
        shell = False
        no_setsid = True
    elif isinstance(cmd, list):
        cmd = ' '.join(cmd)

    preexec = ChildPreExec(personality=None, chrootPath=chrootPath, cwd=cwd,
                           uid=uid, gid=gid, env=environ, shell=shell,
                           unshare_ipc=unshare_ipc, unshare_net=unshare_net,
                           no_setsid=no_setsid)

    if USE_NSPAWN:
        # nspawn cannot set gid
        log.debug("Using nspawn with args %s", nspawn_args)
        cmd = _prepare_nspawn_command(chrootPath, uid, cmd, nspawn_args=nspawn_args, env=environ,
                                      interactive=True, cwd=cwd)
        shell = False

    log.debug("doshell: command: %s", cmd_pretty(cmd))
    return subprocess.call(cmd, preexec_fn=preexec, env=environ, shell=shell)


def run(cmd, isShell=True):
    log = getLog()
    log.debug("run: cmd = %s", cmd_pretty(cmd))
    return subprocess.call(cmd, shell=isShell)


def clean_env():
    return {
        'TERM': 'vt100',
        'SHELL': '/bin/sh',
        'HOME': '/builddir',
        'HOSTNAME': 'mock',
        'PATH': '/usr/bin:/bin:/usr/sbin:/sbin',
        'LANG': 'C.UTF-8',
    }


@traceLog()
def setup_host_resolv(config_opts):
    if not config_opts['use_host_resolv']:
        # If we don't copy host's resolv.conf, we at least want to resolve
        # our own hostname.  See commit 28027fc26d.
        if 'etc/hosts' not in config_opts['files']:
            config_opts['files']['etc/hosts'] = dedent('''\
                127.0.0.1 localhost localhost.localdomain
                ::1       localhost localhost.localdomain localhost6 localhost6.localdomain6
                ''')

    if config_opts['isolation'] == 'simple':
        # Not using nspawn -> don't touch /etc/resolv.conf; we already have
        # a valid file prepared by Buildroot._init() (if user requested).
        return

    if config_opts['rpmbuild_networking'] and not config_opts['use_host_resolv']:
        # keep the default systemd-nspawn's /etc/resolv.conf
        return

    # Either we want to have empty resolv.conf to speedup name resolution
    # failure (rpmbuild_networking is off, see commit 3f939785bb), or we want
    # to copy hosts resolv.conf file.

    resolv_path = (tempfile.mkstemp(prefix="mock-resolv."))[1]
    atexit.register(_nspawnTempResolvAtExit, resolv_path)

    # make sure that anyone in container can read resolv.conf file
    os.chmod(resolv_path, 0o644)

    if config_opts['use_host_resolv']:
        shutil.copyfile('/etc/resolv.conf', resolv_path)

    config_opts['nspawn_args'] += ['--bind={0}:/etc/resolv.conf'.format(resolv_path)]


@traceLog()
def pretty_getcwd():
    try:
        return os.getcwd()
    except OSError:
        if ORIGINAL_CWD is not None:
            return ORIGINAL_CWD
        else:
            return file_util.find_non_nfs_dir()


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


@traceLog()
def createrepo(config_opts, path):
    """ Create repository in given path. """
    cmd = shlex.split(config_opts["createrepo_command"])
    if os.path.exists(os.path.join(path, 'repodata/repomd.xml')):
        cmd.append('--update')
    cmd.append(path)
    return do(cmd)


REPOS_ID = []


@traceLog()
def generate_repo_id(baseurl):
    """ generate repository id for yum.conf out of baseurl """
    repoid = baseurl

    # drop proto:// suffix
    proto_split = baseurl.split('://')
    if len(proto_split) > 1:
        repoid = "/".join(proto_split[1:])
    else:
        repoid = baseurl

    repoid = repoid.replace('/', '_')
    repoid = re.sub(r'[^a-zA-Z0-9_]', '', repoid)
    suffix = ''
    i = 1
    while repoid + suffix in REPOS_ID:
        suffix = str(i)
        i += 1
    repoid = repoid + suffix
    REPOS_ID.append(repoid)
    return repoid


@traceLog()
def add_local_repo(config_opts, baseurl, repoid=None, bootstrap=None):
    if not repoid:
        repoid = generate_repo_id(baseurl)
    else:
        REPOS_ID.append(repoid)
    localyumrepo = """

[{repoid}]
name={baseurl}
baseurl={baseurl}
enabled=1
skip_if_unavailable=0
metadata_expire=0
gpgcheck=0
cost=1
best=1
""".format(repoid=repoid, baseurl=baseurl)

    config_opts['{0}.conf'.format(config_opts['package_manager'])] += localyumrepo

    if bootstrap is None:
        return

    if not baseurl.startswith("file:///") and not baseurl.startswith("/"):
        return

    local_dir = baseurl.replace("file://", "", 1)
    if not local_dir or not os.path.isdir(local_dir):
        return

    mountpoint = bootstrap.make_chroot_path(local_dir)
    bootstrap.mounts.add(BindMountPoint(srcpath=local_dir,
                                        bindpath=mountpoint))


def subscription_redhat_init(opts):
    if not opts['redhat_subscription_required']:
        return

    if 'redhat_subscription_key_id' in opts:
        return

    if not os.path.isdir('/etc/pki/entitlement'):
        raise exception.ConfigError("/etc/pki/entitlment is not a directory, "
                                    "is subscription-manager installed?")

    keys = glob("/etc/pki/entitlement/*-key.pem")
    if not keys:
        raise exception.ConfigError(
            "No key found in /etc/pki/entitlement directory.  It means "
            "this machine is not subscribed.  Please use \n"
            "  1. subscription-manager register\n"
            "  2. subscription-manager list --all --available "
            "(available pool IDs)\n"
            "  3. subscription-manager attach --pool <POOL_ID>\n"
            "If you don't have Red Hat subscription yet, consider "
            "getting subscription:\n"
            "  https://access.redhat.com/solutions/253273\n"
            "You can have a free developer subscription:\n"
            "  https://developers.redhat.com/faq/"
        )

    # Use the first available key.
    key_file_name = os.path.basename(keys[0])
    opts['redhat_subscription_key_id'] = key_file_name.split('-')[0]


def is_host_rh_family():
    distro_name = distro.id()
    return distro_name in RHEL_CLONES + ['fedora']
