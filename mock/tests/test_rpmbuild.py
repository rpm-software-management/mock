"""Unit tests for mockbuild.rpmbuild — command-line assembly."""

from unittest.mock import MagicMock

from mockbuild.rpmbuild import RpmBuild

RPMBUILD_HELP_NEW = """
 -bb                               build binary package only
 -bk                               execute the %check stage
     --clean                       remove build tree when done
     --noclean                     do not execute %clean stage
     --nocheck                     do not execute %check stage
"""

RPMBUILD_HELP_OLD = """
 -bb                               build binary package only
     --clean                       remove build tree when done
     --nocheck                     do not execute %check stage
"""

SPEC = "/builddir/build/SPECS/test.spec"


def _make_rpmbuild(help_output, **config):
    """Return an RpmBuild instance with a stubbed-out buildroot."""
    config_opts = {
        'check': True,
        'cleanup_on_success': True,
        'separate_check': 'off',
        'print_main_output': False,
        'rpmbuild_arch': 'x86_64',
        'rpmbuild_command': '/usr/bin/rpmbuild',
        'rpmbuild_networking': False,
        'rpmbuild_opts': '',
        'rpmbuild_timeout': 0,
    }
    config_opts.update(config)

    RpmBuild._rpmbuild_help_cache = help_output  # pylint: disable=protected-access
    return RpmBuild(MagicMock(), config_opts, SPEC)


def _executed_commands(rpmbuild):
    """Return the list of rpmbuild commands executed in the chroot."""
    # Index the call rather than using call.args, which is Python 3.8+ only.
    # pylint: disable=protected-access
    return [call[0][0][-1] for call in rpmbuild._buildroot.doChroot.call_args_list]


class TestNocleanOption:
    """The %clean stage removes the build directory, see issue#1808."""

    def test_cleanup_on_success(self):
        """Mock never lets rpmbuild run %clean; it does its own cleanup."""
        rpmbuild = _make_rpmbuild(RPMBUILD_HELP_NEW)
        assert rpmbuild.noclean_option == ["--noclean"]

    def test_no_cleanup_on_success(self):
        """The build directory is kept for post-mortem debugging."""
        rpmbuild = _make_rpmbuild(RPMBUILD_HELP_NEW, cleanup_on_success=False)
        assert rpmbuild.noclean_option == ["--noclean"]

    def test_separate_check(self):
        """Separate %check needs the build directory, so %clean is postponed."""
        rpmbuild = _make_rpmbuild(RPMBUILD_HELP_NEW, separate_check='best_effort')
        assert rpmbuild.use_separate_check
        assert rpmbuild.noclean_option == ["--noclean"]

    def test_separate_check_fallback(self):
        """Old rpmbuild has neither -bk nor --noclean, so %clean stays enabled."""
        rpmbuild = _make_rpmbuild(RPMBUILD_HELP_OLD, separate_check='best_effort',
                                  cleanup_on_success=False)
        assert not rpmbuild.use_separate_check
        assert not rpmbuild.noclean_option


class TestRunSeparateCheck:
    """The separate %check phase runs with --noclean; Mock does its own cleanup."""

    def test_check_runs_with_noclean(self):
        """%check runs in isolation and rpmbuild never runs its %clean stage."""
        rpmbuild = _make_rpmbuild(RPMBUILD_HELP_NEW, separate_check='best_effort')
        rpmbuild.run_separate_check()
        assert _executed_commands(rpmbuild) == [
            f"/usr/bin/rpmbuild -bk --short-circuit --noclean --target x86_64 --nodeps {SPEC}",
        ]

    def test_no_cleanup_on_success(self):
        """cleanup_on_success does not change the separate %check invocation."""
        rpmbuild = _make_rpmbuild(RPMBUILD_HELP_NEW, separate_check='best_effort',
                                  cleanup_on_success=False)
        rpmbuild.run_separate_check()
        assert _executed_commands(rpmbuild) == [
            f"/usr/bin/rpmbuild -bk --short-circuit --noclean --target x86_64 --nodeps {SPEC}",
        ]

    def test_check_disabled(self):
        """Nothing is executed when %check doesn't run separately."""
        rpmbuild = _make_rpmbuild(RPMBUILD_HELP_NEW)
        rpmbuild.run_separate_check()
        assert not _executed_commands(rpmbuild)
