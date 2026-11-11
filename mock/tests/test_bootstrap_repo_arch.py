"""Tests for mockbuild.config.get_bootstrap_repo_arch."""

import pytest
from mockbuild.config import get_bootstrap_repo_arch


def _opts(**kwargs):
    opts = {"use_bootstrap_image": False, "repo_arch_map": {}, "host_arch": "x86_64",
            "target_arch": "x86_64", "repo_arch": "x86_64", "legal_host_arches": ("x86_64",)}
    opts.update(kwargs)
    return opts


@pytest.mark.parametrize("kwargs, expected", [
    # Native build.
    ({}, "x86_64"),
    # Emulated target, the bootstrap is native.
    ({"target_arch": "aarch64", "legal_host_arches": ("aarch64",), "repo_arch": "aarch64"}, "x86_64"),
    # Unless bootstrap_forcearch is set.
    ({"target_arch": "aarch64", "legal_host_arches": ("aarch64",), "repo_arch": "aarch64",
      "bootstrap_forcearch": True}, "aarch64"),
    # Multilib keeps the target repositories.
    ({"target_arch": "i686", "legal_host_arches": ("i586", "i686", "x86_64"), "repo_arch": "i386"}, "i386"),
    # A bootstrap image is always native.
    ({"target_arch": "i686", "legal_host_arches": ("i686", "x86_64"), "repo_arch": "i386",
      "use_bootstrap_image": True}, "x86_64"),
    # Except for sub-architectures run natively from the image.
    ({"target_arch": "x86_64_v2", "repo_arch": "x86_64_v2", "use_bootstrap_image": True,
      "oci_platform_map": {"x86_64_v2": "linux/amd64/v2"}}, "x86_64_v2"),
    # The host architecture goes through repo_arch_map.
    ({"host_arch": "armv7l", "target_arch": "aarch64", "legal_host_arches": ("aarch64",),
      "repo_arch": "aarch64", "repo_arch_map": {"armv7l": "armhfp"}}, "armhfp"),
])
def test_get_bootstrap_repo_arch(kwargs, expected):
    """The bootstrap repo_arch follows the host, except for multilib and forced cases."""
    assert get_bootstrap_repo_arch(_opts(**kwargs)) == expected
