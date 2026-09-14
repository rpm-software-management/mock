"""
Thin wrapper for running rpmbuild inside a Mock chroot.
"""

from .exception import BadOption
from .trace_decorator import getLog


class RpmBuild:
    """Thin wrapper for running rpmbuild inside a Mock chroot."""

    _rpmbuild_help_cache = None

    def __init__(self, buildroot, config, spec_path):
        self._buildroot = buildroot
        self._config = config
        self._spec_path = spec_path
        self.last_command = None
        self._resolve_check_flags()

    @property
    def _rpmbuild_help_output(self):
        """Run rpmbuild --help once in the chroot and return (cached) output."""
        if RpmBuild._rpmbuild_help_cache is None:
            output, _ = self._buildroot.doChroot(
                "rpmbuild --help",
                shell=True, raiseExc=False, returnOutput=True,
            )
            RpmBuild._rpmbuild_help_cache = output or ""
        return str(RpmBuild._rpmbuild_help_cache)

    @property
    def noclean_option(self):
        """
        We never want rpmbuild to run the %clean stage.  Mock does its own
        cleanup (commands.clean()), and the %clean stage removes the build
        directory that the separate %check phase (rpmbuild -bk --short-circuit)
        still needs.  So return ["--noclean"] whenever rpmbuild supports it.

        TODO: --noclean is not supported on EL6, remove this check once
        nobody is building for RHEL 6.  See PR#931, #953 and PR#978.
        """
        if "--noclean" in self._rpmbuild_help_output:
            return ["--noclean"]
        return []

    @property
    def supports_bk(self):
        """True if rpmbuild supports -bk for separate %check (rpm >= 6.0.91)."""
        return " -bk" in self._rpmbuild_help_output

    @property
    def _nocheck_option(self):
        """
        EL5/6 does not know --nocheck, so there we use alternative macro override.
        TODO: Remove when nobody needs to build for EL6.
        """
        if "--nocheck" in self._rpmbuild_help_output:
            return ["--nocheck"]
        return ["--define", "'__spec_check_template exit 0; '"]

    def _resolve_check_flags(self):
        """Set self.use_separate_check and self._check_related_flags based on config."""
        self.use_separate_check = False
        self._separate_check_fallback = False

        if not self._config['check']:
            self._check_related_flags = self._nocheck_option
            return

        self._check_related_flags = []

        separate_check = self._config.get('separate_check')
        if separate_check in (None, False, 'off'):
            return

        if separate_check not in ('best_effort', 'enforce'):
            raise BadOption(
                f"Invalid separate_check value: {separate_check}.  "
                "Valid values are 'off', 'best_effort', 'enforce'")

        if not self.supports_bk:
            if separate_check == 'enforce':
                raise BadOption(
                    "separate_check='enforce' requires rpmbuild with -bk support"
                    " (rpm >= 6.0.91)")
            self._separate_check_fallback = True
            return

        self._check_related_flags = self._nocheck_option
        self.use_separate_check = True

    def run(self, args, checkdeps=False, raiseExc=True):
        """Run rpmbuild with given args in the chroot."""
        nodeps = [] if checkdeps else ['--nodeps']
        extra = self._config.get('rpmbuild_opts', '')
        extra_opts = [extra] if extra else []
        command = ([self._config['rpmbuild_command']] + args
                   + self.noclean_option
                   + ['--target', self._config['rpmbuild_arch']] + nodeps
                   + [self._spec_path] + extra_opts)
        command = ["bash", "--login", "-c"] + [' '.join(command)]
        self.last_command = command
        return self._buildroot.doChroot(
            command,
            shell=False, logger=self._buildroot.build_log,
            timeout=self._config['rpmbuild_timeout'],
            uid=self._buildroot.chrootuid, gid=self._buildroot.chrootgid,
            user=self._buildroot.chrootuser,
            unshare_net=not self._config['rpmbuild_networking'],
            raiseExc=raiseExc,
            printOutput=self._config['print_main_output'])

    def run_build(self, args, checkdeps=False, raiseExc=True):
        """Run rpmbuild with check-related flags automatically appended."""
        if self.use_separate_check:
            getLog().info("Skipping %check in main build; it will run as a separate phase later")
        elif self._separate_check_fallback:
            self._buildroot.build_log.warning(
                "rpmbuild does not support -bk, falling back to"
                " monolithic build with %check included")
        return self.run(args + self._check_related_flags,
                        checkdeps=checkdeps, raiseExc=raiseExc)

    def run_separate_check(self):
        """
        Run %check as an isolated phase with artifact dirs protected.

        The main build was run with --noclean (see noclean_option) so that the
        build directory survived for this phase.  We never run rpmbuild's %clean
        stage; Mock removes the build directory as part of its own cleanup
        (commands.clean()).
        """
        if not self.use_separate_check:
            return
        getLog().info("Running %check as a separate phase"
                      " (rpmbuild -bk --short-circuit)")
        with self._buildroot.protect_artifact_dirs():
            self.run(['-bk', '--short-circuit'])
