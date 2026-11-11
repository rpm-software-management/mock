""" Tests for buildroot.py """

from unittest.mock import MagicMock
from mockbuild import util, buildroot


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


def test_installation_time_homedir(tmp_path):
    """ installation_rpm_macros end up in the installation-time .rpmmacros """
    fake = MagicMock()
    fake.rootdir = str(tmp_path)
    fake.config = {"installation_rpm_macros": {"%_db_backend": "ndb"}}
    homedir = buildroot.Buildroot.prepare_installation_time_homedir(fake)
    with open(f"{homedir}/.rpmmacros", encoding="utf-8") as macros:
        assert macros.read() == "%_netsharedpath /proc:/sys\n%_db_backend ndb\n"
