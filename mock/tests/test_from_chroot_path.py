""" Tests for from_chroot_path in buildroot.py """

import pytest
from unittest.mock import MagicMock
from mockbuild import buildroot

def test_from_chroot_path():
    """ test from_chroot_path method """
    config = MagicMock()
    uid_manager = MagicMock()
    state = MagicMock()
    plugins = MagicMock()
    
    # Mock config and rootdir
    config_dict = {
        'root': 'fedora-rawhide-x86_64',
        'basedir': '/var/lib/mock',
        'rootdir': '/var/lib/mock/fedora-rawhide-x86_64/root',
        'resultdir': 'results',
        'chroothome': '/builddir',
        'cache_topdir': '/var/cache/mock',
        'plugin_conf': {'selinux_enable': False},
        'chrootuid': 1000,
        'chrootuser': 'mockbuild',
        'chrootgid': 1000,
        'chrootgroup': 'mock',
        'environment': {},
        'use_buildroot_image': False,
        'buildroot_image': None,
        'buildroot_image_skip_pull': False,
        'buildroot_image_keep_getting': False,
        'additional_packages': [],
        'version': '1.0',
        'files': {},
        'extra_chroot_dirs': [],
        'macros': {},
        'package_manager': 'dnf',
        'tar_binary': 'tar',
        'image_fallback': True,
        'nspawn_args': [],
        'rpm_command': 'rpm',
        'unique-ext': 'none'
    }
    config.__getitem__.side_effect = lambda key: config_dict.get(key)
    config.__contains__.side_effect = lambda key: key in config_dict
    config.get.side_effect = lambda key, default=None: config_dict.get(key, default)
    
    # Initialize Buildroot
    br = buildroot.Buildroot(config, uid_manager, state, plugins)
    br.rootdir = "/var/lib/mock/fedora-rawhide-x86_64/root"
    
    # Test cases
    host_path = "/var/lib/mock/fedora-rawhide-x86_64/root/builddir/build/SPECS/test.spec"
    expected_chroot_path = "/builddir/build/SPECS/test.spec"
    assert br.from_chroot_path(host_path) == expected_chroot_path
    
    # Test path not in rootdir
    other_path = "/tmp/test.spec"
    assert br.from_chroot_path(other_path) == other_path
    
    # Test rootdir without trailing slash
    br.rootdir = "/myroot"
    assert br.from_chroot_path("/myroot/etc/passwd") == "/etc/passwd"
    
    # Test rootdir with trailing slash (should handle it gracefully)
    br.rootdir = "/myroot/"
    assert br.from_chroot_path("/myroot/etc/passwd") == "/etc/passwd"
