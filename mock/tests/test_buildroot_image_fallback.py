"""Tests for container image fallback error reporting"""
# pylint: disable=protected-access

import pytest
from mockbuild import buildroot
from mockbuild.exception import BootstrapError, RootError
from mockbuild.podman import PodmanError


def _make_buildroot(is_bootstrap=False, image_fallback=False):
    """Build a minimally configured Buildroot for _load_from_container_image."""
    br = buildroot.Buildroot.__new__(buildroot.Buildroot)
    br.config = {
        "image_fallback": image_fallback,
        "tar_binary": "/usr/bin/tar",
    }
    br.is_bootstrap = is_bootstrap
    br.use_chroot_image = True
    br.chroot_was_initialized = False
    br.chroot_image = "fedora:latest"
    br.image_skip_pull = False
    br.image_keep_getting = False
    br.image_pull_timeout = 120
    br.make_chroot_path = lambda *paths: "/tmp/chroot"
    return br


def _failing_podman(monkeypatch, message):
    """Patch Podman so that pulling the image fails with the given error."""

    class FailingPodman:
        """Podman stand-in whose image pull always fails."""

        def __init__(self, *args):
            pass

        def retry_image_pull(self, *args, **kwargs):
            """Raise PodmanError to simulate a failed image pull."""
            raise PodmanError(message)

    monkeypatch.setattr(buildroot.util, "mock_host_environment_type", lambda: "")
    monkeypatch.setattr(buildroot, "Podman", FailingPodman)


def test_fallback_disabled_reports_podman_error(monkeypatch):
    """image_fallback disabled surfaces the Podman error, not IndexError"""
    _failing_podman(monkeypatch, "pull access denied")

    br = _make_buildroot(image_fallback=False)
    with pytest.raises(RootError) as excinfo:
        br._load_from_container_image()
    assert "Can't initialize from container image" in str(excinfo.value)
    assert "pull access denied" in str(excinfo.value)


def test_fallback_disabled_bootstrap_error(monkeypatch):
    """bootstrap buildroot raises BootstrapError with the Podman error"""
    _failing_podman(monkeypatch, "registry unreachable")

    br = _make_buildroot(is_bootstrap=True, image_fallback=False)
    with pytest.raises(BootstrapError) as excinfo:
        br._load_from_container_image()
    assert "registry unreachable" in str(excinfo.value)


def test_fallback_enabled_still_falls_back(monkeypatch):
    """image_fallback enabled keeps the existing chroot fallback behaviour"""
    _failing_podman(monkeypatch, "pull access denied")

    br = _make_buildroot(image_fallback=True)
    br._load_from_container_image()
    assert br.use_chroot_image is False
