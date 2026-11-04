""" Tests for buildroot.py """

import fcntl
import multiprocessing
import os
from unittest.mock import MagicMock, patch
from mockbuild import util, buildroot


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
    with open(os.path.join(basedir, "buildroot.lock"), "a+") as lock:
        fcntl.lockf(lock.fileno(), fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        ready.set()
        release.wait(30)


def _try_exclusive(basedir, result):
    """ child process: report whether an exclusive lock can be taken now """
    with open(os.path.join(basedir, "buildroot.lock"), "a+") as lock:
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
