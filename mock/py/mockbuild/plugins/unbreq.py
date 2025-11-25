#!/usr/bin/python3

"""
A plugin which detects unused BuildRequires based on file accesses during the
RPM build.

Author: Marián Konček <mkoncek@redhat.com>
"""

# python library imports
import subprocess
import os
import re
from typing import Generator
from contextlib import contextmanager

# our imports
from mockbuild.trace_decorator import getLog, traceLog
import mockbuild.util
from mockbuild.util import USE_NSPAWN
import mockbuild.mounts
import mockbuild.file_util

requires_api_version = "1.1"

class AtimeDict(dict):
    """
    A caching lazy dictionary mapping file paths to their access time.
    """

    def __missing__(self, key: str) -> float:
        result = os.stat(key).st_atime
        self[key] = result
        return result

@traceLog()
def init(plugins, conf, buildroot) -> None:
    """
    Plugin entry point.
    """
    Unbreq(plugins, conf, buildroot)

class Unbreq:
    """
    Mock plugin that detects unused BuildRequires in RPM builds.

    Works by tracking file access times during the build process to determine
    which packages listed as BuildRequires had their files accessed. Reports any
    BuildRequires fields whose files were not accessed as potentially
    unnecessary.
    """

    # pylint: disable=too-many-instance-attributes
    @traceLog()
    def __init__(self, plugins, conf, buildroot) -> None:
        self.buildroot = buildroot
        self.showrc_opts = conf
        self.config = buildroot.config

        self.enabled = False
        self.chroot_command: list[str] = []
        self.chroot_dnf_command: list[str] = []
        self.min_time: float = 0.0
        config_exclude_accessed_files = (
            self.config
            .get("plugin_conf", {})
            .get("unbreq_opts", {})
            .get("exclude_accessed_files", [])
        )
        if not isinstance(config_exclude_accessed_files, list):
            raise mockbuild.exception.ConfigError("unbreq plugin: expected configuration field "
                f"`exclude_accessed_files` to be a list, but was {type(config_exclude_accessed_files)}"
            )
        self.exclude_accessed_files = [re.compile(r) for r in config_exclude_accessed_files]
        self.accessed_files = AtimeDict()
        self.mount_options: list[str] = []
        self.buildrequires_providers: dict[str, list[str]] = {}
        self.buildrequires_deptype: dict[str, str] = {}

        # TODO handle different package managers
        # self.buildroot.pkg_manager.name

        plugins.add_hook("earlyprebuild", self._EarlyPrebuildHook)
        plugins.add_hook("postyum", self._PostYumHook)
        plugins.add_hook("postdeps", self._PostDepsHook)
        plugins.add_hook("postbuild", self._PostBuildHook)

    @traceLog()
    @contextmanager
    def do_with_chroot(self) -> Generator:
        """
        Provide context for execution with having the mock chroot mounted in
        the bootstrap chroot, if available.
        """
        # NOTE this should really be handled automatically by `buildroot_in_bootstrap_mounted`.
        if not USE_NSPAWN and self.buildroot.bootstrap_buildroot is not None:
            with self.buildroot.shadow_utils.root.uid_manager.elevated_privileges():
                with self.buildroot.mounts.buildroot_in_bootstrap_mounted():
                    yield
        else:
            yield

    @traceLog()
    def get_buildrequires(self, srpm: str) -> None:
        """
        Get the BuildRequires fields of a SRPM file and store them in `self.buildrequires_deptype`
        mapped to their dependency type.
        We recognize the following dependency types:
          * rpmlib - disregard these, we cannot use them in dnf queries
          * manual - explicitly written in the .spec file
          * auto - result of dynamic BuildRequires generation
        Dependency type strings can have more attributes separated by a comma.
        We ignore those.
        """
        process = subprocess.run(self.chroot_command + ["/usr/bin/rpm", "--root", self.buildroot.rootdir, "-q",
            "--qf", "[%{REQUIREFLAGS:deptype} %{REQUIRES} %{REQUIREFLAGS:depflags} %{REQUIREVERSION}\\n]", srpm],
            stdin = subprocess.DEVNULL, stdout = subprocess.PIPE, stderr = subprocess.PIPE,
            text = True, check = True,
        )
        for line in process.stdout.splitlines():
            separator = line.find(" ")
            deptype_end = line.find(",", 0, separator)
            if deptype_end == -1:
                deptype_end = separator
            deptype = line[:deptype_end]
            buildrequires = line[separator + 1:].rstrip()
            if deptype == "rpmlib":
                continue
            self.buildrequires_deptype[buildrequires] = deptype

    @traceLog()
    def get_files(self, packages: list[str]) -> list[str]:
        """
        Get the files owned by `packages` using an RPM query.
        """
        if len(packages) == 0:
            return []
        process = subprocess.run(self.chroot_command +
            ["/usr/bin/rpm", "--root", self.buildroot.rootdir, "-q", "--qf", "[%{FILENAMES}\\n]"] + packages,
            stdin = subprocess.DEVNULL, stdout = subprocess.PIPE, stderr = subprocess.PIPE,
            text = True, check = True,
        )
        result = process.stdout.splitlines()
        return result

    @traceLog()
    def try_remove(self, packages: list[str]) -> list[str]:
        """
        Try to remove `packages` and obtain all the packages (NVRs) that would be removed.
        """

        # Note that we expect this command to return 1
        process = subprocess.run(self.chroot_dnf_command +
            ["--setopt", "protected_packages=", "--assumeno", "remove"] + packages,
            stdin = subprocess.DEVNULL, stdout = subprocess.PIPE, stderr = subprocess.PIPE,
            text = True, check = False,
        )
        if process.returncode != 1:
            raise subprocess.CalledProcessError(
                process.returncode, " ".join(process.args), process.stdout, process.stderr
            )
        result = []
        for line in process.stdout.splitlines():
            if not line.startswith(" "):
                continue
            nvr = line.split()
            if len(nvr) != 6:
                continue
            result.append(f"{nvr[0]}-{nvr[2]}.{nvr[1]}")
        return result

    @traceLog()
    def get_buildrequires_providers(self, buildrequires: list[str]) -> dict[str, list[str]]:
        """
        Get the mapping of BuildRequires fields to the RPMs that provide it.
        Each BR can be provided by multiple installed RPMs but we try to
        minimize it.
        """

        # Get both the mapping and the reverse mapping between each
        # BuildRequires field and the RPMs that provide it.
        br_providers: dict[str, list[str]] = {}
        provided_brs: dict[str, list[str]] = {}
        for br in buildrequires:
            process = subprocess.run(
                self.chroot_dnf_command + ["repoquery", "--installed", "--whatprovides", br],
                stdin = subprocess.DEVNULL, stdout = subprocess.PIPE, stderr = subprocess.PIPE,
                text = True, check = True,
            )
            current_br_providers: list[str] = process.stdout.splitlines()
            br_providers[br] = current_br_providers
            for provider in current_br_providers:
                provided_brs.setdefault(provider, []).append(br)

        # We work with the assumption that the package manager installed the
        # minimal set of packages. In case we encounter a BR provided by
        # multiple RPMs, it will be because there are other BRs which are
        # provided by only one of them.
        # So sort the BR mapping by the number of providers from the shortest
        # one and if the same RPM provider is found providing a different BR,
        # remove it from the other list.

        # pylint: disable=too-many-nested-blocks,invalid-name
        sorted_br_providers = sorted(br_providers, key = lambda k: len(br_providers[k]))
        if len(sorted_br_providers) != 0 and len(sorted_br_providers[-1]) > 1:
            for br in sorted_br_providers:
                current_br_providers = br_providers[br]
                if len(current_br_providers) == 1:
                    for provided_br in provided_brs[current_br_providers[0]]:
                        if provided_br != br:
                            provided_brs_of_current_br_provider = br_providers[provided_br]
                            if len(provided_brs_of_current_br_provider) > 1:
                                try:
                                    provided_brs_of_current_br_provider.remove(current_br_providers[0])
                                except ValueError:
                                    pass
        return br_providers

    @traceLog()
    def resolve_buildrequires(self) -> None:
        """
        Decide which BuildRequires fields were not used based on file accesses.
        """
        brs_can_be_removed: list[tuple[str, list[str]]] = []
        for br, providers in self.buildrequires_providers.items():
            removed_packages = self.try_remove([v for vs in brs_can_be_removed for v in vs[1]] + providers)
            can_be_removed = True
            for path in self.get_files(removed_packages):
                path = self.buildroot.make_chroot_path(path)
                try:
                    atime = self.accessed_files[path]
                except FileNotFoundError:
                    continue
                if atime > self.min_time:
                    short_path = path[len(self.buildroot.rootdir):]
                    for r in self.exclude_accessed_files:
                        if r.search(short_path) is not None:
                            break
                    else:
                        getLog().info(
                            "unbreq plugin: BuildRequires %s is needed because file %s was accessed",
                            br, short_path
                        )
                        can_be_removed = False
                        break
            if can_be_removed:
                brs_can_be_removed.append((br, providers))
        if len(brs_can_be_removed) != 0:
            brs = list(map(lambda t: t[0], brs_can_be_removed))
            getLog().warning("unbreq plugin: the following BuildRequires were not used:\n\t%s", "\n\t".join(brs))

    @traceLog()
    def set_br_files_am_time(self) -> None:
        """
        Get all the BuildRequires, the RPMs that provide them, the files they
        own and set both their access and modify timestamps to zero.
        """
        buildrequires_providers = []
        for providers in self.buildrequires_providers.values():
            buildrequires_providers.extend(providers)

        for path in set(self.get_files(self.try_remove(buildrequires_providers))):
            try:
                os.utime(self.buildroot.make_chroot_path(path), (0, 0))
            except FileNotFoundError:
                pass

    @traceLog()
    def _EarlyPrebuildHook(self) -> None:
        """
        Initialize some chroot attributes.
        """
        self.enabled = True

        getLog().info("enabled unbreq plugin (earlyprebuild)")

        if self.buildroot.bootstrap_buildroot is not None:
            if USE_NSPAWN:
                self.chroot_command = ["/usr/bin/systemd-nspawn", "--quiet", "--pipe",
                    "-D", self.buildroot.bootstrap_buildroot.rootdir, "--bind", self.buildroot.rootdir
                ]
            else:
                self.chroot_command = ["/usr/sbin/chroot", self.buildroot.bootstrap_buildroot.rootdir]
        self.chroot_dnf_command = self.chroot_command + ["/usr/bin/dnf", "--installroot", self.buildroot.rootdir]

    @traceLog()
    def _PostYumHook(self) -> None:
        """
        This is called multiple times, but only this hook catches the potential
        temporary SRPM containing dynamically generated BuildRequires.
        We simply collect them every time this hook is invoked.
        """
        if not self.enabled:
            return

        getLog().info("enabled unbreq plugin (postyum)")

        srpm_dir = self.buildroot.make_chroot_path(self.buildroot.builddir, "SRPMS")
        with self.do_with_chroot():
            for srpm in os.scandir(srpm_dir):
                self.get_buildrequires(srpm.path)

    @traceLog()
    def _PostDepsHook(self) -> None:
        """
        At this point even dynamic BuildRequires have been generated.
        """
        if not self.enabled:
            return

        getLog().info("enabled unbreq plugin (postdeps)")

        with self.do_with_chroot():
            self.buildrequires_providers = self.get_buildrequires_providers(sorted(self.buildrequires_deptype.keys()))

        # NOTE maybe find a better example file to touch to get an atime?
        path = self.buildroot.make_chroot_path("dev", "null")
        mockbuild.file_util.touch(path)
        self.min_time = os.path.getatime(path)

        try:
            # NOTE should failure throw an exception?
            mount_options_process = subprocess.run(
                ["/usr/bin/findmnt", "-n", "-o", "OPTIONS", "--target", self.buildroot.rootdir],
                stdin = subprocess.DEVNULL, stdout = subprocess.PIPE, stderr = subprocess.PIPE,
                text = True, check = False,
            )
            if mount_options_process:
                self.mount_options = mount_options_process.stdout.rstrip().split(",")
            else:
                getLog().warning("unbreq plugin: unable to detect buildroot mount options, process %s returned %d: %s",
                    mount_options_process, mount_options_process.returncode, mount_options_process.stderr,
                )
        except FileNotFoundError:
            pass

        if "relatime" in self.mount_options:
            getLog().info(
                "unbreq plugin: detected 'relatime' mount option, setting access times of files under %s to 0",
                self.buildroot.rootdir
            )
            with self.do_with_chroot():
                self.set_br_files_am_time()

    @traceLog()
    def _PostBuildHook(self) -> None:
        """
        Resolve accessed files to BuildRequires.
        """
        if not self.enabled or self.buildroot.state.result != "success":
            return

        getLog().info("enabled unbreq plugin (postbuild)")

        if "noatime" in self.mount_options:
            getLog().warning(
                "unbreq plugin: chroot %s is on a filesystem mounted with the 'noatime' option;"
                "detection will not work correctly,"
                "you may want to remount the proper directory with mount options 'strictatime,lazytime'",
                self.buildroot.rootdir
            )
        with self.do_with_chroot():
            self.resolve_buildrequires()
