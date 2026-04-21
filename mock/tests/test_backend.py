# -*- coding: utf-8 -*-
"""Unit tests for mockbuild.backend — copy helpers."""

import os
import stat
from unittest.mock import MagicMock

from mockbuild.backend import Commands


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
