# -*- coding: utf-8 -*-
"""Unit tests for mockbuild.backend — copy helpers."""

import os
import stat
from unittest.mock import MagicMock

from mockbuild.backend import Commands
from mockbuild.buildroot import Buildroot
from mockbuild.config import setup_default_config_opts


def _make_scrub_commands(tmp_path):
    """Return a Commands instance with stubbed buildroots and real cache directories."""
    cache = tmp_path / "cache"
    bootstrap_cache = tmp_path / "bootstrap_cache"
    cache.mkdir()
    bootstrap_cache.mkdir()
    for directory in (cache, bootstrap_cache):
        for name in ("root_cache", "ccache", "yum_cache", "dnf_cache", "other"):
            subdir = directory / name
            subdir.mkdir()
            (subdir / "entry").write_text("cached data")

    cmd = Commands.__new__(Commands)
    cmd.buildroot = MagicMock(cachedir=str(cache), selinux=False)
    cmd.bootstrap_buildroot = MagicMock(cachedir=str(bootstrap_cache), selinux=False)
    cmd.plugins = MagicMock()
    cmd.state = MagicMock()
    cmd.config_name = "test"
    return cmd


def _make_commands(tmp_path):
    """Return a Commands instance with a stubbed-out buildroot."""
    originals = tmp_path / "chroot" / "builddir" / "originals"
    originals.mkdir(parents=True)

    br = MagicMock()
    br.builddir = "/builddir"
    br.make_chroot_path = lambda *parts: str(tmp_path / "chroot" / os.path.join(*parts).lstrip("/"))

    cmd = Commands.__new__(Commands)
    cmd.buildroot = br
    return cmd


def _make_uniqueext_commands(tmp_path, monkeypatch, uniqueext):
    """Return Commands with real buildroots confined to temporary directories."""
    monkeypatch.setattr("mockbuild.util.USE_NSPAWN", False)
    monkeypatch.setattr("mockbuild.util.orphansKill", MagicMock())
    monkeypatch.setattr("mockbuild.util.find_btrfs_in_chroot", MagicMock(return_value=None))
    monkeypatch.setattr("mockbuild.buildroot.mounts.Mounts", MagicMock())

    cmd = Commands.__new__(Commands)
    for root, is_bootstrap in (("test", False), ("test-bootstrap", True)):
        config = setup_default_config_opts()
        config['root'] = root
        config['unique-ext'] = uniqueext
        config['basedir'] = str(tmp_path / "buildroots")
        config['cache_topdir'] = str(tmp_path / "caches")
        config['chrootgid'] = os.getgid()
        config['backup_on_clean'] = False
        config['plugin_conf']['selinux_enable'] = True
        config['__jinja_expand'] = True
        buildroot = Buildroot(config, MagicMock(), MagicMock(), MagicMock(), is_bootstrap=is_bootstrap)
        os.makedirs(buildroot.rootdir)
        os.makedirs(buildroot.cachedir, exist_ok=True)
        if is_bootstrap:
            cmd.bootstrap_buildroot = buildroot
        else:
            cmd.buildroot = buildroot

    cmd.plugins = MagicMock()
    cmd.state = MagicMock()
    cmd.config_name = "test"
    return cmd


class TestScrub:
    """Each scrub value removes only its intended chroots or caches."""

    def test_chroot(self, tmp_path):
        """Scrubbing the main chroot preserves the bootstrap chroot and both caches."""
        cmd = _make_scrub_commands(tmp_path)

        cmd.scrub(["chroot"])

        cmd.buildroot.delete.assert_called_once_with()
        cmd.bootstrap_buildroot.delete.assert_not_called()
        assert (tmp_path / "cache").is_dir()
        assert (tmp_path / "bootstrap_cache").is_dir()

    def test_cache(self, tmp_path):
        """Scrubbing cache removes the entire main cache without deleting chroots."""
        cmd = _make_scrub_commands(tmp_path)

        cmd.scrub(["cache"])

        cmd.buildroot.delete.assert_not_called()
        cmd.bootstrap_buildroot.delete.assert_not_called()
        assert not (tmp_path / "cache").exists()
        assert (tmp_path / "bootstrap_cache").is_dir()

    def test_root_cache(self, tmp_path):
        """Only the main root cache is removed, preserving other caches and chroots."""
        cmd = _make_scrub_commands(tmp_path)

        cmd.scrub(["root-cache"])

        cmd.buildroot.delete.assert_not_called()
        cmd.bootstrap_buildroot.delete.assert_not_called()
        assert set(os.listdir(cmd.buildroot.cachedir)) == {"ccache", "yum_cache", "dnf_cache", "other"}
        assert set(os.listdir(cmd.bootstrap_buildroot.cachedir)) == {
            "root_cache", "ccache", "yum_cache", "dnf_cache", "other",
        }

    def test_c_cache(self, tmp_path):
        """Only the main compiler cache is removed, preserving other caches and chroots."""
        cmd = _make_scrub_commands(tmp_path)

        cmd.scrub(["c-cache"])

        cmd.buildroot.delete.assert_not_called()
        cmd.bootstrap_buildroot.delete.assert_not_called()
        assert set(os.listdir(cmd.buildroot.cachedir)) == {"root_cache", "yum_cache", "dnf_cache", "other"}
        assert set(os.listdir(cmd.bootstrap_buildroot.cachedir)) == {
            "root_cache", "ccache", "yum_cache", "dnf_cache", "other",
        }

    def test_yum_cache(self, tmp_path):
        """Yum cache cleanup removes both package manager caches only from the main buildroot."""
        cmd = _make_scrub_commands(tmp_path)

        cmd.scrub(["yum-cache"])

        cmd.buildroot.delete.assert_not_called()
        cmd.bootstrap_buildroot.delete.assert_not_called()
        assert set(os.listdir(cmd.buildroot.cachedir)) == {"root_cache", "ccache", "other"}
        assert set(os.listdir(cmd.bootstrap_buildroot.cachedir)) == {
            "root_cache", "ccache", "yum_cache", "dnf_cache", "other",
        }

    def test_dnf_cache(self, tmp_path):
        """Dnf cache cleanup is an alias for removing both main package manager caches."""
        cmd = _make_scrub_commands(tmp_path)

        cmd.scrub(["dnf-cache"])

        cmd.buildroot.delete.assert_not_called()
        cmd.bootstrap_buildroot.delete.assert_not_called()
        assert set(os.listdir(cmd.buildroot.cachedir)) == {"root_cache", "ccache", "other"}
        assert set(os.listdir(cmd.bootstrap_buildroot.cachedir)) == {
            "root_cache", "ccache", "yum_cache", "dnf_cache", "other",
        }

    def test_lvm(self, tmp_path):
        """LVM cleanup is dispatched to plugins for both buildroots without removing caches."""
        cmd = _make_scrub_commands(tmp_path)

        cmd.scrub(["lvm"])

        cmd.plugins.call_hooks.assert_any_call("scrub", "lvm")
        cmd.bootstrap_buildroot.plugins.call_hooks.assert_any_call("scrub", "lvm")
        cmd.buildroot.delete.assert_not_called()
        cmd.bootstrap_buildroot.delete.assert_not_called()
        assert (tmp_path / "cache").is_dir()
        assert (tmp_path / "bootstrap_cache").is_dir()

    def test_overlayfs(self, tmp_path):
        """OverlayFS cleanup is dispatched to plugins for both buildroots without removing caches."""
        cmd = _make_scrub_commands(tmp_path)

        cmd.scrub(["overlayfs"])

        cmd.plugins.call_hooks.assert_any_call("scrub", "overlayfs")
        cmd.bootstrap_buildroot.plugins.call_hooks.assert_any_call("scrub", "overlayfs")
        cmd.buildroot.delete.assert_not_called()
        cmd.bootstrap_buildroot.delete.assert_not_called()
        assert (tmp_path / "cache").is_dir()
        assert (tmp_path / "bootstrap_cache").is_dir()

    def test_bootstrap_preserves_cache(self, tmp_path):
        """Scrubbing the bootstrap chroot preserves both caches and the main chroot."""
        cmd = _make_scrub_commands(tmp_path)

        cmd.scrub(["bootstrap"])

        cmd.bootstrap_buildroot.delete.assert_called_once_with()
        cmd.buildroot.delete.assert_not_called()
        assert (tmp_path / "cache").is_dir()
        assert (tmp_path / "bootstrap_cache").is_dir()

    def test_bootstrap_cache_preserves_chroots(self, tmp_path):
        """Scrubbing the bootstrap cache preserves both chroots and the main cache."""
        cmd = _make_scrub_commands(tmp_path)

        cmd.scrub(["bootstrap-cache"])

        cmd.bootstrap_buildroot.delete.assert_not_called()
        cmd.buildroot.delete.assert_not_called()
        assert (tmp_path / "cache").is_dir()
        assert not (tmp_path / "bootstrap_cache").exists()

    def test_bootstrap_and_cache(self, tmp_path):
        """Combining both options removes the bootstrap chroot and its cache."""
        cmd = _make_scrub_commands(tmp_path)

        cmd.scrub(["bootstrap", "bootstrap-cache"])

        cmd.bootstrap_buildroot.delete.assert_called_once_with()
        cmd.buildroot.delete.assert_not_called()
        assert (tmp_path / "cache").is_dir()
        assert not (tmp_path / "bootstrap_cache").exists()

    def test_all(self, tmp_path):
        """Scrubbing all still removes both chroots and their caches."""
        cmd = _make_scrub_commands(tmp_path)

        cmd.scrub(["all"])

        cmd.bootstrap_buildroot.delete.assert_called_once_with()
        cmd.buildroot.delete.assert_called_once_with()
        assert not (tmp_path / "cache").exists()
        assert not (tmp_path / "bootstrap_cache").exists()

    def test_bootstrap_without_bootstrap_buildroot(self, tmp_path):
        """Scrubbing a missing bootstrap chroot preserves the main chroot and caches."""
        cmd = _make_scrub_commands(tmp_path)
        cmd.bootstrap_buildroot = None

        cmd.scrub(["bootstrap"])

        cmd.buildroot.delete.assert_not_called()
        assert (tmp_path / "cache").is_dir()
        assert (tmp_path / "bootstrap_cache").is_dir()

    def test_bootstrap_cache_without_buildroot(self, tmp_path):
        """Scrubbing without a bootstrap buildroot leaves cache directories untouched."""
        cmd = _make_scrub_commands(tmp_path)
        cmd.bootstrap_buildroot = None

        cmd.scrub(["bootstrap-cache"])

        cmd.buildroot.delete.assert_not_called()
        assert (tmp_path / "cache").is_dir()
        assert (tmp_path / "bootstrap_cache").is_dir()


class TestScrubUniqueext:
    """Unique extensions isolate chroots while their caches remain shared."""

    def test_bootstrap(self, tmp_path, monkeypatch):
        """Only the selected bootstrap chroot is removed, preserving shared caches."""
        cmd = _make_uniqueext_commands(tmp_path, monkeypatch, "selected")
        other = _make_uniqueext_commands(tmp_path, monkeypatch, "other")

        cmd.scrub(["bootstrap"])

        assert not os.path.exists(cmd.bootstrap_buildroot.basedir)
        assert os.path.isdir(cmd.buildroot.basedir)
        assert os.path.isdir(other.buildroot.basedir)
        assert os.path.isdir(other.bootstrap_buildroot.basedir)
        assert os.path.isdir(other.buildroot.cachedir)
        assert os.path.isdir(other.bootstrap_buildroot.cachedir)

    def test_bootstrap_cache(self, tmp_path, monkeypatch):
        """The shared bootstrap cache is removed without deleting any chroots."""
        cmd = _make_uniqueext_commands(tmp_path, monkeypatch, "selected")
        other = _make_uniqueext_commands(tmp_path, monkeypatch, "other")

        cmd.scrub(["bootstrap-cache"])

        assert os.path.isdir(cmd.buildroot.basedir)
        assert os.path.isdir(cmd.bootstrap_buildroot.basedir)
        assert os.path.isdir(other.buildroot.basedir)
        assert os.path.isdir(other.bootstrap_buildroot.basedir)
        assert os.path.isdir(other.buildroot.cachedir)
        assert not os.path.exists(cmd.bootstrap_buildroot.cachedir)
        assert not os.path.exists(other.bootstrap_buildroot.cachedir)

    def test_bootstrap_and_cache(self, tmp_path, monkeypatch):
        """Combined cleanup removes the selected bootstrap chroot and shared cache."""
        cmd = _make_uniqueext_commands(tmp_path, monkeypatch, "selected")
        other = _make_uniqueext_commands(tmp_path, monkeypatch, "other")

        cmd.scrub(["bootstrap", "bootstrap-cache"])

        assert not os.path.exists(cmd.bootstrap_buildroot.basedir)
        assert os.path.isdir(cmd.buildroot.basedir)
        assert os.path.isdir(other.buildroot.basedir)
        assert os.path.isdir(other.bootstrap_buildroot.basedir)
        assert os.path.isdir(other.buildroot.cachedir)
        assert not os.path.exists(other.bootstrap_buildroot.cachedir)

    def test_all(self, tmp_path, monkeypatch):
        """All removes selected chroots and shared caches but preserves other chroots."""
        cmd = _make_uniqueext_commands(tmp_path, monkeypatch, "selected")
        other = _make_uniqueext_commands(tmp_path, monkeypatch, "other")

        cmd.scrub(["all"])

        assert not os.path.exists(cmd.buildroot.basedir)
        assert not os.path.exists(cmd.bootstrap_buildroot.basedir)
        assert os.path.isdir(other.buildroot.basedir)
        assert os.path.isdir(other.bootstrap_buildroot.basedir)
        assert not os.path.exists(other.buildroot.cachedir)
        assert not os.path.exists(other.bootstrap_buildroot.cachedir)


class TestCopySpecIntoChroot:
    """copy_spec_into_chroot must not preserve restrictive permissions."""

    def test_restrictive_permissions_not_preserved(self, tmp_path):
        """A 0600 spec file must become 0644 after copy (#1300)."""
        spec = tmp_path / "test.spec"
        spec.write_text("Name: test\n")
        spec.chmod(0o600)

        cmd = _make_commands(tmp_path)
        cmd.copy_spec_into_chroot(str(spec))

        dest = tmp_path / "chroot" / "builddir" / "originals" / "test.spec"
        mode = stat.S_IMODE(dest.stat().st_mode)
        assert mode == 0o644, f"file should be 0644, got {oct(mode)}"

    def test_content_copied(self, tmp_path):
        """File content must be faithfully copied."""
        spec = tmp_path / "hello.spec"
        spec.write_text("Name: hello\nVersion: 1\n")

        cmd = _make_commands(tmp_path)
        cmd.copy_spec_into_chroot(str(spec))

        dest = tmp_path / "chroot" / "builddir" / "originals" / "hello.spec"
        assert dest.read_text() == "Name: hello\nVersion: 1\n"

    def test_return_value(self, tmp_path):
        """Returned path must be the in-chroot (non-host) path."""
        spec = tmp_path / "foo.spec"
        spec.write_text("")

        cmd = _make_commands(tmp_path)
        result = cmd.copy_spec_into_chroot(str(spec))
        assert result == "/builddir/originals/foo.spec"


class TestCopySrpmIntoChroot:
    """copy_srpm_into_chroot basic behavior."""

    def test_content_copied(self, tmp_path):
        """File content must be faithfully copied."""
        srpm = tmp_path / "test.src.rpm"
        srpm.write_bytes(b"\x00" * 16)

        cmd = _make_commands(tmp_path)
        cmd.copy_srpm_into_chroot(str(srpm))

        dest = tmp_path / "chroot" / "builddir" / "originals" / "test.src.rpm"
        assert dest.read_bytes() == b"\x00" * 16

    def test_return_value(self, tmp_path):
        """Returned path must be the in-chroot (non-host) path."""
        srpm = tmp_path / "test.src.rpm"
        srpm.write_bytes(b"")

        cmd = _make_commands(tmp_path)
        result = cmd.copy_srpm_into_chroot(str(srpm))
        assert result == "/builddir/originals/test.src.rpm"
