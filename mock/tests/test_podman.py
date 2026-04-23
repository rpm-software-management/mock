# -*- coding: utf-8 -*-
"""Unit tests for mockbuild.podman — OCI platform pull and architecture check."""

import subprocess
from unittest.mock import MagicMock, patch

from mockbuild.podman import (
    Podman,
    podman_check_native_image_architecture,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_buildroot(target_arch, oci_platform_map=None):
    """Return a minimal mock buildroot with the given config values."""
    config = {"target_arch": target_arch}
    if oci_platform_map is not None:
        config["oci_platform_map"] = oci_platform_map
    br = MagicMock()
    br.config = config
    br.env = {}
    return br


def _make_podman(buildroot, image="registry.example.com/image:latest"):
    """Instantiate Podman while bypassing the os.path.exists check."""
    with patch("os.path.exists", return_value=True):
        return Podman(buildroot, image)


# ===================================================================
# R002 — pull_image injects --platform when mapping matches
# ===================================================================

class TestPullImagePlatform:
    """pull_image() must inject --platform from oci_platform_map."""

    @patch("mockbuild.podman.subprocess.run")
    def test_platform_injected_when_mapped(self, mock_run):
        """--platform linux/amd64/v2 appears when target_arch is x86_64_v2."""
        mock_run.return_value = MagicMock(returncode=0, stdout=b"sha256:abc")
        br = _make_buildroot(
            "x86_64_v2",
            oci_platform_map={"x86_64_v2": "linux/amd64/v2"},
        )
        pod = _make_podman(br)
        assert pod.pull_image() is True

        cmd = mock_run.call_args[0][0]
        assert "--platform" in cmd
        plat_idx = cmd.index("--platform")
        assert cmd[plat_idx + 1] == "linux/amd64/v2"
        # --platform must precede image name
        assert plat_idx < cmd.index("registry.example.com/image:latest")

    @patch("mockbuild.podman.subprocess.run")
    def test_no_platform_when_arch_not_in_map(self, mock_run):
        """--platform absent when target_arch has no mapping entry."""
        mock_run.return_value = MagicMock(returncode=0, stdout=b"sha256:abc")
        br = _make_buildroot(
            "x86_64",
            oci_platform_map={"x86_64_v2": "linux/amd64/v2"},
        )
        pod = _make_podman(br)
        assert pod.pull_image() is True

        cmd = mock_run.call_args[0][0]
        assert "--platform" not in cmd

    @patch("mockbuild.podman.subprocess.run")
    def test_no_platform_when_map_missing(self, mock_run):
        """--platform absent when oci_platform_map key is missing entirely."""
        mock_run.return_value = MagicMock(returncode=0, stdout=b"sha256:def")
        br = _make_buildroot("x86_64")  # no oci_platform_map
        pod = _make_podman(br)
        assert pod.pull_image() is True

        cmd = mock_run.call_args[0][0]
        assert "--platform" not in cmd

    @patch("mockbuild.podman.subprocess.run")
    def test_empty_target_arch(self, mock_run):
        """Empty target_arch string never produces --platform."""
        mock_run.return_value = MagicMock(returncode=0, stdout=b"sha256:ghi")
        br = _make_buildroot(
            "",
            oci_platform_map={"x86_64_v2": "linux/amd64/v2"},
        )
        pod = _make_podman(br)
        assert pod.pull_image() is True

        cmd = mock_run.call_args[0][0]
        assert "--platform" not in cmd


# ===================================================================
# R003 — podman_check_native_image_architecture
# ===================================================================

class TestArchCheck:
    """Architecture check compares system vs image os/arch."""

    @patch("mockbuild.podman.subprocess.check_output")
    def test_matching_arch_returns_true(self, mock_co):
        """Matching system and image arch returns True."""
        mock_co.side_effect = ["linux/amd64", "linux/amd64"]
        assert podman_check_native_image_architecture("img:latest") is True

    @patch("mockbuild.podman.subprocess.check_output")
    def test_mismatched_arch_returns_false(self, mock_co):
        """Mismatched system and image arch returns False."""
        mock_co.side_effect = ["linux/amd64", "linux/arm64"]
        assert podman_check_native_image_architecture("img:latest") is False


# ===================================================================
# Negative / boundary tests
# ===================================================================

class TestPullImageTimeout:
    """pull_image() must handle timeout correctly."""

    @patch("mockbuild.podman.subprocess.run")
    def test_timeout_passed_to_subprocess(self, mock_run):
        """timeout parameter is forwarded to subprocess.run."""
        mock_run.return_value = MagicMock(returncode=0, stdout=b"sha256:abc")
        br = _make_buildroot("x86_64")
        pod = _make_podman(br)
        assert pod.pull_image(timeout=60) is True
        assert mock_run.call_args[1]["timeout"] == 60

    @patch("mockbuild.podman.subprocess.run")
    def test_timeout_expired_returns_false(self, mock_run):
        """TimeoutExpired causes pull_image to return False."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="podman pull", timeout=60)
        br = _make_buildroot("x86_64")
        pod = _make_podman(br)
        assert pod.pull_image(timeout=60) is False

    @patch("mockbuild.podman.subprocess.run")
    def test_no_timeout_by_default(self, mock_run):
        """Without timeout argument, subprocess.run gets timeout=None."""
        mock_run.return_value = MagicMock(returncode=0, stdout=b"sha256:abc")
        br = _make_buildroot("x86_64")
        pod = _make_podman(br)
        pod.pull_image()
        assert mock_run.call_args[1]["timeout"] is None


class TestArchCheckErrorPaths:
    """Error handling in architecture check."""

    @patch("mockbuild.podman.subprocess.check_output")
    def test_subprocess_error_returns_false(self, mock_co):
        """SubprocessError during check returns False (existing behavior)."""
        mock_co.side_effect = subprocess.SubprocessError("fail")
        assert podman_check_native_image_architecture("img:latest") is False
