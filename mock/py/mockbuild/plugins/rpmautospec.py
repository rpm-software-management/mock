# -*- coding: utf-8 -*-
# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# License: GPL2 or later see COPYING
# Copyright (C) 2023 Stephen Gallagher <sgallagh@redhat.com>
# Copyright (C) 2023 Nils Philippsen <nils@redhat.com>
"""A mock plugin to pre-process spec files using rpmautospec."""

from pathlib import Path
from typing import Optional, Union

from rpmautospec_core import specfile_uses_rpmautospec

from mockbuild.exception import ConfigError, PkgError
from mockbuild.trace_decorator import getLog, traceLog

requires_api_version = "1.1"


@traceLog()
def init(plugins, conf, buildroot):
    """Register the rpmautospec plugin with mock."""
    RpmautospecPlugin(plugins, conf, buildroot)


class RpmautospecPlugin:
    """Fill in release and changelog from git history using rpmautospec"""

    @traceLog()
    def __init__(self, plugins, conf, buildroot):
        self.buildroot = buildroot
        self.config = buildroot.config
        self.opts = conf
        self.log = getLog()

        if "cmd_base" not in self.opts:
            raise ConfigError("The 'rpmautospec_opts.cmd_base' is unset")

        plugins.add_hook("pre_srpm_build", self.attempt_process_distgit)
        self.log.info("rpmautospec: initialized")

    @traceLog()
    def attempt_process_distgit(
        self,
        host_chroot_spec: Union[Path, str],
        host_chroot_sources: Optional[Union[Path, str]],
    ) -> None:
        """Attempt to process a spec file with rpmautospec."""
        # Set up variables and check prerequisites.
        if not host_chroot_sources:
            self.log.debug("Sources not specified, skipping rpmautospec preprocessing.")
            return

        host_chroot_spec = Path(host_chroot_spec)
        host_chroot_sources = Path(host_chroot_sources)
        if not host_chroot_sources.is_dir():
            self.log.debug(
                "Sources not a directory, skipping rpmautospec preprocessing."
            )
            return

        distgit_git_dir = host_chroot_sources / ".git"
        if not distgit_git_dir.is_dir():
            self.log.debug(
                "Sources is not a git repository, skipping rpmautospec preprocessing."
            )
            return

        host_chroot_sources_spec = host_chroot_sources / host_chroot_spec.name
        if not host_chroot_sources_spec.is_file():
            self.log.debug(
                "Sources doesn’t contain spec file, skipping rpmautospec preprocessing."
            )
            return

        with host_chroot_spec.open("rb") as spec, host_chroot_sources_spec.open(
            "rb"
        ) as sources_spec:
            if spec.read() != sources_spec.read():
                self.log.warning(
                    "Spec file inside and outside sources are different, skipping rpmautospec"
                    " preprocessing."
                )
                return

        if not specfile_uses_rpmautospec(host_chroot_sources_spec):
            self.log.debug(
                "Spec file doesn’t use rpmautospec, skipping rpmautospec preprocessing."
            )
            return

        # Install the `rpmautospec` command line tool into the build root.
        if self.opts.get("requires", None):
            try:
                self.buildroot.pkg_manager.install_as_root(*self.opts["requires"], check=True)
            except Exception as exc:
                raise PkgError(
                    "Can’t install rpmautospec dependencies into chroot: "
                    + ", ".join(self.opts["requires"])
                ) from exc

        # Get paths inside the chroot by chopping off the leading paths
        chroot_dir = Path(self.buildroot.make_chroot_path())
        chroot_spec = Path("/") / host_chroot_spec.relative_to(chroot_dir)
        chroot_sources = Path("/") / host_chroot_sources.relative_to(chroot_dir)
        chroot_sources_spec = Path("/") / host_chroot_sources_spec.relative_to(chroot_dir)

        # Call subprocess to perform the specfile rewrite
        command = list(self.opts["cmd_base"])
        command += [chroot_sources_spec]  # <input-spec>
        command += [chroot_spec]  # <output-spec>

        # Run the rpmautospec tool in the chroot sandbox. This minimizes
        # external dependencies in the host, e.g. the Koji build system. As a
        # bonus, spec files will be processed in the environment they will be
        # built for, reducing the impact of the host system on the outcome,
        # leading to more deterministic results and better repeatable builds.
        self.buildroot.doChroot(
            command,
            shell=False,
            cwd=chroot_sources,
            logger=self.buildroot.build_log,
            uid=self.buildroot.chrootuid,
            gid=self.buildroot.chrootgid,
            user=self.buildroot.chrootuser,
            unshare_net=not self.config.get("rpmbuild_networking", False),
            nspawn_args=self.config.get("nspawn_args", []),
            printOutput=self.config.get("print_main_output", True),
        )
