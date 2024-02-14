"""
Tests for mockbuild.config
"""

# pylint: disable=missing-class-docstring
# pylint: disable=missing-function-docstring
# pylint: disable=attribute-defined-outside-init

import pwd
import os
import shutil
import tempfile

from unittest import mock
from mockbuild.config import simple_load_config


class TestConfigLoader:
    def setup_method(self):
        testdir = os.path.dirname(os.path.realpath(__file__))
        self.configdir = os.path.join(testdir, "data", "config-001")
        self.homedir = tempfile.mkdtemp(prefix='mock-test-home')
        homedata = os.path.join(testdir, "data", "home-001")
        self.username = pwd.getpwuid(os.getuid())[0]
        userdir = os.path.join(self.homedir, self.username)
        shutil.copytree(homedata, userdir)

    def test_config_paths(self):
        with mock.patch("mockbuild.config.os.path.expanduser") as patch:
            patch.side_effect = lambda x: x.replace("~", self.homedir + "/")
            config = simple_load_config('fedora-rawhide-x86_64', self.configdir)
        assert set(config["config_paths"]) == {
            os.path.join(self.configdir, "site-defaults.cfg"),
            os.path.join(self.configdir, "fedora-rawhide-x86_64.cfg"),
            os.path.join(self.configdir, "templates", "fedora-rawhide.tpl"),
            os.path.join(self.homedir, self.username, ".config", "mock.cfg"),
            os.path.join(self.homedir, self.username, ".config", "mock", "fedora-rawhide-x86_64.cfg"),
        }

        assert config["default"] is True
        assert config["target_arch"] == 'x86_64'
        assert config["template"] == "templated_value"
        assert config["home_default"] == (1, 2)

        assert config["override_wins_site"] == "site"
        assert config["override_wins_conf"] == "conf"
        assert config["override_wins_home_site"] == "home_site"
        assert config["override_wins_home_conf"] == "home_conf"
        assert config["override_wins_template"] == "template"

    def teardown_method(self):
        shutil.rmtree(self.homedir)
