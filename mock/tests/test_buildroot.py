""" Tests for buildroot.py """
# pylint: disable=protected-access

import fcntl
import multiprocessing
import os
from unittest.mock import MagicMock, patch

import pytest

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
    """ a Buildroot with just enough state for the locking code """
    root = buildroot.Buildroot.__new__(buildroot.Buildroot)
    root.basedir = basedir
    root.is_bootstrap = False
    root._lock_file = None
    return root


def _hold_lock(basedir, ready, release):
    """ child process: hold the buildroot lock as shared, the way a running
    Mock process does once initialize() has finished """
    with open(os.path.join(basedir, "buildroot.lock"), "a+",
              encoding="utf-8") as lock:
        fcntl.lockf(lock.fileno(), fcntl.LOCK_SH)
        ready.set()
        release.wait(30)


def _can_lock_exclusively(basedir):
    """ whether another process could take the buildroot lock now """
    with open(os.path.join(basedir, "buildroot.lock"), "a+",
              encoding="utf-8") as lock:
        try:
            fcntl.lockf(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            return False


def test_initialize_free_buildroot(tmp_path):
    """ an unused buildroot is initialized and stays locked as shared """
    basedir = str(tmp_path)
    root = _bare_buildroot(basedir)
    with patch.object(root, "_init") as init:
        root.initialize()
    try:
        init.assert_called_once_with(prebuild=False)
        ctx = multiprocessing.get_context("fork")
        with ctx.Pool(1) as pool:
            assert pool.apply(_can_lock_exclusively, (basedir,)) is False
    finally:
        root._unlock_buildroot()


def test_initialize_refuses_busy_buildroot(tmp_path):
    """ a buildroot another Mock process holds is not touched """
    basedir = str(tmp_path)
    ctx = multiprocessing.get_context("fork")
    ready, release = ctx.Event(), ctx.Event()
    other = ctx.Process(target=_hold_lock, args=(basedir, ready, release))
    other.start()
    assert ready.wait(30)
    root = _bare_buildroot(basedir)
    try:
        with patch.object(root, "_init") as init, \
                patch.object(root, "set_package_manager") as set_pkg_mgr, \
                pytest.raises(BuildRootLocked, match="--uniqueext"):
            root.initialize()
        init.assert_not_called()
        set_pkg_mgr.assert_not_called()
    finally:
        root._unlock_buildroot()
        release.set()
        other.join(30)
