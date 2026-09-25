"""Tests for util.host_path_to_chroot_path."""

from mockbuild.util import host_path_to_chroot_path


def test_host_path_to_chroot_path():
    """Boundary-safe host-to-chroot path conversion."""
    rootdir = "/var/lib/mock/fedora-rawhide-x86_64/root"
    host_path = (
        "/var/lib/mock/fedora-rawhide-x86_64/root/builddir/build/SPECS/test.spec"
    )
    assert host_path_to_chroot_path(host_path, rootdir) == (
        "/builddir/build/SPECS/test.spec"
    )

    # Path not under rootdir is unchanged.
    assert host_path_to_chroot_path("/tmp/test.spec", rootdir) == "/tmp/test.spec"

    # rootdir without trailing slash
    assert host_path_to_chroot_path("/myroot/etc/passwd", "/myroot") == "/etc/passwd"

    # rootdir with trailing slash
    assert host_path_to_chroot_path("/myroot/etc/passwd", "/myroot/") == "/etc/passwd"

    # Exact rootdir maps to "/"
    assert host_path_to_chroot_path("/myroot", "/myroot") == "/"
    assert host_path_to_chroot_path("/myroot/", "/myroot") == "/"

    # Sibling prefix must not be treated as inside rootdir
    assert host_path_to_chroot_path(
        "/myroot-other/etc/passwd", "/myroot"
    ) == "/myroot-other/etc/passwd"
