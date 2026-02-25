import os
import unittest
from unittest.mock import MagicMock, patch
import sys
from pathlib import Path

# Add mock/py to sys.path so we can import mockbuild
sys.path.insert(0, str(Path(__file__).parents[2] / "mock" / "py"))

from mockbuild.plugins.sbom_generator import SBOMGenerator

class TestSBOMGenerator(unittest.TestCase):
    def setUp(self):
        self.plugins = MagicMock()
        self.conf = {}
        self.buildroot = MagicMock()
        self.buildroot.rootdir = "/var/lib/mock/fedora-rawhide-x86_64/root"
        self.buildroot.builddir = "/builddir"
        self.buildroot.from_chroot_path = MagicMock(side_effect=lambda x: x.replace(self.buildroot.rootdir, ""))
        
        # Mocking root_log
        self.buildroot.root_log = MagicMock()
        
        self.generator = SBOMGenerator(self.plugins, self.conf, self.buildroot)

    @patch('os.path.isfile')
    @patch('os.path.isdir')
    @patch('os.path.exists')
    @patch('os.path.getsize')
    def test_parse_spec_file_with_specfile_library(self, mock_getsize, mock_exists, mock_isdir, mock_isfile):
        # We need to mock isfile for the spec file itself
        def side_effect_isfile(path):
            if path == "/builddir/SPECS/test.spec":
                return True
            return False
            
        mock_isfile.side_effect = side_effect_isfile
        mock_exists.return_value = True
        
        spec_content = """
Name: test-package
Version: 1.0.0
Release: 1
Summary: A test package
License: MIT

Source0: https://example.com/source1.tar.gz
Source1: source2.tar.gz#sha256:1234567890abcdef
Patch0: patch1.diff

%description
A test package for unit testing SBOM generator.

%files
"""
        # Mock doChroot to return the expanded spec content
        self.buildroot.doChroot.return_value = (spec_content, 0)
        
        # Mock hash_file to return a dummy hash
        with patch.object(SBOMGenerator, 'hash_file', return_value="deadbeef"):
            # Mock get_file_signature
            with patch.object(SBOMGenerator, 'get_file_signature', return_value=None):
                # We also need to mock os.path.dirname and os.path.join if they behave differently on host
                # but standard ones should be fine.
                
                sources = self.generator.parse_spec_file("/builddir/SPECS/test.spec")
                
                # Should have 3 items: source1, source2, and patch1
                self.assertEqual(len(sources), 3)
                
                # Verify source 0 (from URL)
                self.assertEqual(sources[0]['filename'], "source1.tar.gz")
                
                # Verify source 1 (with inline hash)
                self.assertEqual(sources[1]['filename'], "source2.tar.gz")
                self.assertEqual(sources[1]['sha256'], "sha256:1234567890abcdef")
                
                # Verify patch 0
                self.assertEqual(sources[2]['filename'], "patch1.diff")

if __name__ == '__main__':
    unittest.main()
