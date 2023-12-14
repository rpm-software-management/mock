"""Test the rpmautospec plugin."""

from copy import deepcopy
from pathlib import Path
from unittest import mock

import pytest

from mockbuild.exception import ConfigError, PkgError
from mockbuild.plugins import rpmautospec
from mockbuild.util import nullcontext

UNSET = object()


@mock.patch("mockbuild.plugins.rpmautospec.RpmautospecPlugin")
def test_init(RpmautospecPlugin):  # pylint: disable=invalid-name
    """Test the function which registers the plugin."""
    plugins = object()
    conf = object()
    buildroot = object()

    rpmautospec.init(plugins, conf, buildroot)

    RpmautospecPlugin.assert_called_once_with(plugins, conf, buildroot)


class TestRpmautospecPlugin:
    """Test the RpmautospecPlugin class."""

    DEFAULT_OPTS = {
        "requires": ["rpmautospec"],
        "cmd_base": ["rpmautospec", "process-distgit"],
    }

    def create_plugin(self, plugins=UNSET, conf=UNSET, buildroot=UNSET):
        """Create a plugin object and prepare it for testing."""
        if plugins is UNSET:
            plugins = mock.Mock()
        if conf is UNSET:
            conf = deepcopy(self.DEFAULT_OPTS)
        if buildroot is UNSET:
            buildroot = mock.Mock()

        return rpmautospec.RpmautospecPlugin(plugins, conf, buildroot)

    @pytest.mark.parametrize(
        "with_cmd_base", (True, False), ids=("with-cmd_base", "without-cmd_base")
    )
    @mock.patch("mockbuild.plugins.rpmautospec.getLog")
    def test___init__(self, getLog, with_cmd_base):
        """Test the constructor."""
        plugins = mock.Mock()

        conf = deepcopy(self.DEFAULT_OPTS)
        if with_cmd_base:
            expectation = nullcontext()
        else:
            expectation = pytest.raises(ConfigError)
            del conf["cmd_base"]

        buildroot = mock.Mock()

        with expectation as exc_info:
            logger = getLog.return_value
            plugin = self.create_plugin(plugins=plugins, conf=conf, buildroot=buildroot)

        if with_cmd_base:
            assert plugin.buildroot is buildroot
            assert plugin.config is buildroot.config
            assert plugin.opts is conf
            assert plugin.log is logger
            plugins.add_hook.assert_called_once_with("pre_srpm_build", plugin.attempt_process_distgit)
            logger.info.assert_called_once_with("rpmautospec: initialized")
        else:
            assert "rpmautospec_opts.cmd_base" in str(exc_info.value)

    @pytest.mark.parametrize(
        "testcase",
        (
            "happy-path",
            "happy-path-no-requires",
            "without-sources",
            "sources-not-dir",
            "sources-not-repo",
            "sources-no-specfile",
            "spec-files-different",
            "specfile-no-rpmautospec",
            "broken-requires",
        ),
    )
    def test_attempt_process_distgit(
        self, testcase, tmp_path
    ):  # pylint: disable=too-many-branches disable=too-many-statements disable=too-many-locals
        """Test the attempt_process_distgit() method."""
        # Set the stage
        plugin = self.create_plugin()
        plugin.log = log = mock.Mock()
        plugin.buildroot.make_chroot_path.return_value = str(tmp_path)
        if "no-requires" in testcase:
            plugin.opts["requires"] = []

        spec_dir = tmp_path / "SPECS"
        spec_dir.mkdir()
        sources_dir = tmp_path / "SOURCES"
        sources_dir.mkdir()

        host_chroot_spec = spec_dir / "pkg.spec"
        host_chroot_sources = sources_dir / "pkg"
        host_chroot_sources.mkdir()
        host_chroot_sources_git = host_chroot_sources / ".git"
        host_chroot_sources_spec = host_chroot_sources / "pkg.spec"

        if "no-rpmautospec" not in testcase:
            spec_contents = (
                "Release: %autorelease",
                "%changelog",
                "%autochangelog",
            )
        else:
            spec_contents = (
                "Release: 1",
                "%changelog",
            )

        with host_chroot_spec.open("w") as fp:
            for line in spec_contents:
                print(line, file=fp)

        if "without-sources" in testcase:
            host_chroot_sources = None
        elif "sources-not-dir" not in testcase:
            if "sources-no-specfile" not in testcase:
                with host_chroot_sources_spec.open("w") as fp:
                    if "spec-files-different" in testcase:
                        print("# BOO", file=fp)
                    for line in spec_contents:
                        print(line, file=fp)
            if "sources-not-repo" not in testcase:
                host_chroot_sources_git.mkdir()
        else:
            host_chroot_sources = tmp_path / "pkg.tar"
            host_chroot_sources.touch()

        if "broken-requires" in testcase:
            plugin.buildroot.install_as_root.side_effect = RuntimeError("FAIL")
            expect_exception = pytest.raises(PkgError)
        else:
            expect_exception = nullcontext()

        with expect_exception as excinfo:
            plugin.attempt_process_distgit(host_chroot_spec, host_chroot_sources)

        if "happy-path" in testcase:
            chroot_spec = Path("/") / host_chroot_spec.relative_to(tmp_path)
            chroot_sources = Path("/") / host_chroot_sources.relative_to(tmp_path)
            chroot_sources_spec = Path("/") / host_chroot_sources_spec.relative_to(tmp_path)

            expected_command = plugin.opts["cmd_base"] + [chroot_sources_spec, chroot_spec]

            plugin.buildroot.doChroot.assert_called_once_with(
                expected_command,
                shell=False,
                cwd=chroot_sources,
                logger=plugin.buildroot.build_log,
                uid=plugin.buildroot.chrootuid,
                gid=plugin.buildroot.chrootgid,
                user=plugin.buildroot.chrootuser,
                unshare_net=not plugin.config.get("rpmbuild_networking", False),
                nspawn_args=plugin.config.get("nspawn_args", []),
                printOutput=plugin.config.get("print_main_output", True),
            )
        else:
            plugin.buildroot.doChroot.assert_not_called()
            if "broken-requires" not in testcase:
                if "spec-files-different" in testcase:
                    log_method = log.warning
                else:
                    log_method = log.debug
                log_method.assert_called_once()
                log_string = log_method.call_args[0][0]
                assert "skipping rpmautospec preprocessing" in log_string

                if "without-sources" in testcase:
                    assert "Sources not specified" in log_string
                elif "sources-not-dir" in testcase:
                    assert "Sources not a directory" in log_string
                elif "sources-not-repo" in testcase:
                    assert "Sources is not a git repository" in log_string
                elif "sources-no-specfile" in testcase:
                    assert "Sources doesn’t contain spec file" in log_string
                elif "spec-files-different" in testcase:
                    assert "Spec file inside and outside sources are different" in log_string
                elif "specfile-no-rpmautospec" in testcase:
                    assert "Spec file doesn’t use rpmautospec" in log_string
            else:
                assert str(excinfo.value) == (
                    "Can’t install rpmautospec dependencies into chroot: "
                    + ", ".join(self.DEFAULT_OPTS["requires"])
                )
