"""
Test the methods that generate buildroot_lock.json
"""

import json
import os
import tempfile
from unittest import TestCase
from unittest.mock import MagicMock, patch
import jsonschema

from mockbuild.plugins.buildroot_lock import init
import mockbuild.exception

# gpg-pubkey packages stay ignored
# fedora-release is normal package with simple license
RPM_OUTPUT = """\
gpg-pubkey|/@(none)|/@pubkey|/@105ef944|/@65ca83d1|/@(none)|/@(none)|/@(none)
gpg-pubkey|/@(none)|/@pubkey|/@e99d6ad1|/@64d2612c|/@(none)|/@(none)|/@(none)
fedora-release|/@noarch|/@MIT|/@42|/@0.3|/@(none)|/@cf31d87e5e3eac97ff32a98e7e073f37|/@(none)
bash|/@x86_64|/@GPLv3+|/@5.1.8|/@9.el9|/@(none)|/@57e93b1739cc3512f9f29dcaa8a38055|/@RSA/SHA256, Sun Mar 31 12:41:20 2024, Key ID 199e2f91fd431d51
"""  # noqa: E501

# cyrus-sasl-lib is not present in the REPOQUERY_OUTPUT
RPM_ONLY_RPM = """\
cyrus-sasl-lib|/@x86_64|/@BSD with advertising|/@2.1.27|/@21.el9|/@(none)|/@9e1caba09fac94568419b9dfd14fb4c5|/@RSA/SHA256, Mon Sep 12 23:24:22 2022, Key ID 199e2f91fd431d51
"""  # noqa: E501

REPOQUERY_OUTPUT = """\
http://ftp.fi.muni.cz/pub/linux/fedora/linux/development/rawhide/Everything/x86_64/os/Packages/f/fedora-release-42-0.3.noarch.rpm
https://cdn.redhat.com/content/dist/rhel9/9/x86_64/baseos/os/Packages/b/bash-5.1.8-9.el9.x86_64.rpm
"""

EXPECTED_OUTPUT = {
    'version': '1.0.0',
    'buildroot': {
        'rpms': [{
            'arch': 'x86_64',
            'epoch': None,
            'license': 'GPLv3+',
            'name': 'bash',
            'release': '9.el9',
            'sigmd5': '57e93b1739cc3512f9f29dcaa8a38055',
            'signature': 'fd431d51',
            'url': 'https://cdn.redhat.com/content/dist/rhel9/9/x86_64'
                   '/baseos/os/Packages/b/bash-5.1.8-9.el9.x86_64.rpm',
            'version': '5.1.8'
        }, {
            'arch': 'noarch',
            'epoch': None,
            'license': 'MIT',
            'name': 'fedora-release',
            'release': '0.3',
            'sigmd5': 'cf31d87e5e3eac97ff32a98e7e073f37',
            'signature': None,
            'url': 'http://ftp.fi.muni.cz/pub/linux/fedora/linux'
                   '/development/rawhide/Everything/x86_64/os'
                   '/Packages/f/fedora-release-42-0.3.noarch.rpm',
            'version': '42',
        }]
    },
    "bootstrap": {
        "image_digest": "sha256:ba1067bef190fbe88f085bd019464a8c0803b7cd1e3f",
    },
    'config': {
        'bootstrap_image': 'foo',
        'bootstrap_image_ready': True,
        "legal_host_arches": ["x86_64"],
        "target_arch": "x86_64",
        "dist": ".f42",
    },
}


def _mock_vars(rpm_out, repoquery_out):
    tc = TestCase()
    tc.maxDiff = None
    buildroot = MagicMock()
    buildroot.state = MagicMock()
    buildroot.uid_manager = MagicMock()
    buildroot.doOutChroot = MagicMock(
        side_effect=iter([
            (rpm_out, None),
            (repoquery_out, None),
        ])
    )
    buildroot.config = EXPECTED_OUTPUT['config']
    buildroot.resultdir = tempfile.mkdtemp(prefix="mock-test-buildroot-lock")
    plugins = MagicMock()
    plugins.add_hook = MagicMock()
    return tc, buildroot, plugins


def _call_method(plugins, buildroot):
    # initialize the plugin
    init(plugins, {}, buildroot)
    # obtain the hook method, and call it
    plugins.add_hook.assert_called_once()
    _, method = plugins.add_hook.call_args[0]

    podman_obj = MagicMock()
    podman_obj.get_oci_digest.return_value = EXPECTED_OUTPUT["bootstrap"]["image_digest"]
    podman_cls = MagicMock(return_value=podman_obj)
    with patch("mockbuild.plugins.buildroot_lock.Podman", side_effect=podman_cls):
        method()


def test_nonexisting_file_in_repo():
    """
    Test the situation when RPM is installed, and no longer available in
    repository.
    """
    _, buildroot, plugins = _mock_vars(
        RPM_OUTPUT + RPM_ONLY_RPM,
        REPOQUERY_OUTPUT,
    )
    raised = False
    try:
        _call_method(plugins, buildroot)
    except mockbuild.exception.Error as e:
        assert e.msg == "Can't get location for cyrus-sasl-lib.x86_64"
        raised = True
    assert raised


def _get_json_schema():
    testdir = os.path.dirname(__file__)
    basename = "buildroot-lock-schema-" + EXPECTED_OUTPUT["version"] + ".json"
    with open(os.path.join(testdir, "..", "docs", basename),
              "r", encoding="utf-8") as fd:
        return json.load(fd)


def test_buildroot_lock_output():
    """ test the buildroot_lock.json file format """
    tc, buildroot, plugins = _mock_vars(RPM_OUTPUT, REPOQUERY_OUTPUT)
    _call_method(plugins, buildroot)
    with open(os.path.join(buildroot.resultdir, "buildroot_lock.json"), "r",
              encoding="utf-8") as fd:
        data = json.load(fd)
    tc.assertDictEqual(data, EXPECTED_OUTPUT)
    schema = _get_json_schema()
    jsonschema.validate(EXPECTED_OUTPUT, schema)


def test_json_schema_metadata():
    """ Test basic format of the json schema """
    schema = _get_json_schema()
    version = EXPECTED_OUTPUT["version"]
    assert "Version " + version + ";" in schema["description"]
    assert "schema-" + version + ".json" in schema["$id"]
