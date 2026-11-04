""" Tests for buildroot.py """

# pylint: disable=protected-access

import fcntl
import logging
import multiprocessing
import os
import subprocess
import threading
from unittest.mock import MagicMock, patch
from mockbuild import util, buildroot
from mockbuild.exception import BuildRootLocked


def test_module_config():
    """ test _module_commands_from_config method """
    def _check(config, output):
        assert buildroot.Buildroot._module_commands_from_config(config) \
            == output
    _check([("enable", "module:stream")],
           [["module", "enable", "module:stream"]])
    _check([("enable", "module:stream, module2:stream2")],
           [["module", "enable", "module:stream", "module2:stream2"]])
    _check([("disable", "module:*,module2:*"),
            ("enable", "module:stream, module2:stream2"),
            ("install", "pg:12")],
           [["module", "disable", "module:*", "module2:*"],
            ["module", "enable", "module:stream", "module2:stream2"],
            ["module", "install", "pg:12"]])

    _check([("info", "")], [["module", "info"]])
    _check([("info", None)], [["module", "info"]])


def _bare_buildroot(basedir):
    """ a Buildroot with just enough state for the lock/device helpers """
    root = buildroot.Buildroot.__new__(buildroot.Buildroot)
    root.basedir = basedir
    root.rootdir = os.path.join(basedir, "root")
    root._lock_file = None
    root._lock_exclusive = False
    return root


def _hold_lock(basedir, exclusive, ready, release):
    """ child process: hold the buildroot lock until told to release it """
    with open(os.path.join(basedir, "buildroot.lock"), "a+", encoding="utf-8") as lock:
        fcntl.lockf(lock.fileno(), fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        ready.set()
        release.wait(30)


def _try_exclusive(basedir, result):
    """ child process: report whether an exclusive lock can be taken now """
    with open(os.path.join(basedir, "buildroot.lock"), "a+", encoding="utf-8") as lock:
        try:
            fcntl.lockf(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            result.value = 1
        except OSError:
            result.value = 0


def test_other_users_present(tmp_path):
    """ other_users_present() detects a concurrent holder of the lock and
    keeps our own shared lock either way """
    ctx = multiprocessing.get_context("fork")
    basedir = str(tmp_path)
    root = _bare_buildroot(basedir)

    # not holding the lock: cannot tell, keep the old behaviour
    assert root.other_users_present() is False

    root._lock_buildroot(exclusive=False)
    assert root.other_users_present() is False

    ready, release = ctx.Event(), ctx.Event()
    other = ctx.Process(target=_hold_lock, args=(basedir, False, ready, release))
    other.start()
    assert ready.wait(30)
    try:
        assert root.other_users_present() is True
    finally:
        release.set()
        other.join(30)

    assert root.other_users_present() is False

    # we must still hold our shared lock after the check
    result = ctx.Value("i", -1)
    probe = ctx.Process(target=_try_exclusive, args=(basedir, result))
    probe.start()
    probe.join(30)
    assert result.value == 0

    root._unlock_buildroot()
    probe = ctx.Process(target=_try_exclusive, args=(basedir, result))
    probe.start()
    probe.join(30)
    assert result.value == 1


def test_other_users_present_exclusive(tmp_path):
    """ holding the exclusive lock means nobody else uses the buildroot """
    root = _bare_buildroot(str(tmp_path))
    root._lock_buildroot(exclusive=True)
    assert root.other_users_present() is False
    assert root._lock_exclusive is True
    root._unlock_buildroot()


@patch("os.path.ismount")
def test_register_device_bindmounts(ismount, tmp_path):
    """ device nodes another process bind-mounted are tracked """
    root = _bare_buildroot(str(tmp_path))
    root.config = {"internal_dev_setup": True, "dev_loop_count": 2}
    root.mounts = MagicMock()
    already = MagicMock(mountpath=root.make_chroot_path("dev/zero"))
    root.mounts.essential_mounts = [already]
    mounted = {root.make_chroot_path(p) for p in ("dev/null", "dev/zero")}
    ismount.side_effect = lambda path: path in mounted

    root._register_device_bindmounts()

    root.mounts.add_device_bindmount.assert_called_once_with("/dev/null")


def test_register_device_bindmounts_disabled(tmp_path):
    """ nothing to do without internal_dev_setup """
    root = _bare_buildroot(str(tmp_path))
    root.config = {"internal_dev_setup": False}
    root.mounts = MagicMock()
    root._register_device_bindmounts()
    root.mounts.add_device_bindmount.assert_not_called()


def test_shared_lock_retries(tmp_path):
    """ a shared lock request waits out another process's brief exclusive
    lock (e.g. other_users_present() upgrading its lock) instead of failing """
    ctx = multiprocessing.get_context("fork")
    basedir = str(tmp_path)
    ready, release = ctx.Event(), ctx.Event()
    other = ctx.Process(target=_hold_lock, args=(basedir, True, ready, release))
    other.start()
    assert ready.wait(30)
    timer = threading.Timer(0.2, release.set)
    timer.start()
    root = _bare_buildroot(basedir)
    try:
        root._lock_buildroot(exclusive=False)
        assert root._lock_exclusive is False
    finally:
        release.set()
        timer.cancel()
        other.join(30)
        root._unlock_buildroot()


def test_exclusive_lock_does_not_retry(tmp_path):
    """ an exclusive lock request still fails at once if the lock is held """
    ctx = multiprocessing.get_context("fork")
    basedir = str(tmp_path)
    ready, release = ctx.Event(), ctx.Event()
    other = ctx.Process(target=_hold_lock, args=(basedir, False, ready, release))
    other.start()
    assert ready.wait(30)
    root = _bare_buildroot(basedir)
    try:
        with patch("time.sleep") as sleep:
            try:
                root._lock_buildroot(exclusive=True)
                assert False, "exclusive lock taken while another process holds it"
            except BuildRootLocked:
                pass
            sleep.assert_not_called()
    finally:
        release.set()
        other.join(30)
        root._unlock_buildroot()


def test_join_registers_devices_late(tmp_path):
    """ a process joining an initialized buildroot looks for device bind
    mounts only once it holds the shared lock, i.e. once the initializing
    process is done creating them """
    root = _bare_buildroot(str(tmp_path))
    calls = []

    def lock(exclusive):
        calls.append("lock_ex" if exclusive else "lock_sh")
        if exclusive:
            raise BuildRootLocked("locked")

    with patch.object(root, "_lock_buildroot", side_effect=lock), \
            patch.object(root, "set_package_manager",
                         side_effect=lambda: calls.append("pkg_mgr")), \
            patch.object(root, "_register_device_bindmounts",
                         side_effect=lambda: calls.append("register")):
        root.initialize()

    assert calls == ["lock_ex", "pkg_mgr", "lock_sh", "register"]


def _run_with_orphan(chroot_path, kill_orphans):
    """ run a command that exits while leaving a child holding its output
    open, the way logOutput() sees leftover processes in a chroot; return
    the paths orphansKill() was asked to clean up """
    with subprocess.Popen(["sh", "-c", "sleep 3 & exit 0"],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE) as child, \
            patch("mockbuild.util.orphansKill") as orphans_kill:
        util.logOutput(child.stdout, child.stderr, logging.getLogger("test"),
                       returnOutput=0, child=child, chrootPath=chroot_path,
                       kill_orphans=kill_orphans)
        return [c.args[0] for c in orphans_kill.call_args_list]


def test_orphans_killed_when_alone(tmp_path):
    """ with nobody else using the buildroot, orphans are still killed """
    basedir = str(tmp_path)
    root = _bare_buildroot(basedir)
    root._lock_buildroot(exclusive=False)
    try:
        killed = _run_with_orphan(basedir, lambda: not root.other_users_present())
    finally:
        root._unlock_buildroot()
    assert killed == [basedir]


def test_orphans_kept_if_user_joins_late(tmp_path):
    """ the decision to kill orphans is made when the command has finished:
    a mock process that joined the buildroot while the command was running
    must not have its processes killed (issue 1836) """
    ctx = multiprocessing.get_context("fork")
    basedir = str(tmp_path)
    root = _bare_buildroot(basedir)
    root._lock_buildroot(exclusive=False)
    # nobody else yet: an eager check would decide to kill
    assert root.other_users_present() is False

    ready, release = ctx.Event(), ctx.Event()
    other = ctx.Process(target=_hold_lock, args=(basedir, False, ready, release))

    def join_later():
        other.start()
        ready.wait(30)

    joiner = threading.Timer(0.1, join_later)
    joiner.start()
    try:
        killed = _run_with_orphan(basedir, lambda: not root.other_users_present())
    finally:
        joiner.join(30)
        release.set()
        other.join(30)
        root._unlock_buildroot()
    assert not killed
