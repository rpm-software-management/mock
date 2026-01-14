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
from typing import Any, Generator, Iterable, Iterator, Optional
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

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

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.lock = Lock()

    def __missing__(self, key: str) -> float:
        result = os.stat(key).st_atime
        with self.lock:
            self[key] = result
        return result

@traceLog()
def _run_subprocess(
    command: list[str], *args: Any, expected_returncode: int = 0, **kwargs: Any
) -> subprocess.CompletedProcess:
    """
    Helper function which calls `subprocess.run` but logs standard outputs in
    case of a failure.
    """
    kwargs.setdefault("stdin", subprocess.DEVNULL)
    kwargs.setdefault("stdout", subprocess.PIPE)
    kwargs.setdefault("stderr", subprocess.PIPE)
    kwargs.setdefault("text", True)
    kwargs.pop("check", None)

    getLog().debug("unbreq plugin: Executing command: %s", command)

    # Use `check` explicitly to silence linters.
    process = subprocess.run(command, *args, check = False, **kwargs)
    if process.returncode != expected_returncode:
        for line in process.stdout.splitlines():
            getLog().error("%s", line)
        for line in process.stderr.splitlines():
            getLog().error("%s", line)
        raise subprocess.CalledProcessError(
            process.returncode, mockbuild.util.cmd_pretty(process.args), process.stdout, process.stderr
        )
    return process

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
        self.chroot_rpm_command: list[str] = []
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
        self.srpms: set[str] = set()
        self.rpm_files: dict[str, list[str]] = {}
        self.buildrequires_providers: dict[str, list[str]] = {}
        self.buildrequires_deptype: dict[str, str] = {}
        self.pool: ThreadPoolExecutor = ThreadPoolExecutor(max_workers = os.process_cpu_count() or 1)

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
        if not USE_NSPAWN:
            with self.buildroot.shadow_utils.root.uid_manager.elevated_privileges():
                if self.buildroot.bootstrap_buildroot is not None:
                    with self.buildroot.mounts.buildroot_in_bootstrap_mounted():
                        yield
                else:
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
        process = _run_subprocess([*self.chroot_rpm_command, "-q", "--qf",
            "[%{REQUIREFLAGS:deptype} %{REQUIRES} %{REQUIREFLAGS:depflags} %{REQUIREVERSION}\\n]", srpm],
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
    def get_files(self, packages: set[str]) -> Iterator[str]:
        """
        Get the files owned by `packages` using an RPM query.
        """
        queried_packages = packages.difference(self.rpm_files.keys())
        if len(queried_packages) != 0:
            process = _run_subprocess([*self.chroot_rpm_command, "-q",
                "--qf", "\\n[%{FILENAMES}\\n]", *queried_packages],
            )
            package_it = iter(queried_packages)
            for line in process.stdout.splitlines():
                if not line:
                    package = next(package_it)
                    current_files: list[str] = []
                    self.rpm_files[package] = current_files
                else:
                    current_files.append(line)
        return (path for package in packages for path in self.rpm_files[package])

    @traceLog()
    def try_remove(self, packages: Iterator[str]) -> set[str]:
        """
        Try to remove `packages` and obtain all the packages (NVRs) that would be removed.
        """

        # Note that we expect this command to return 1
        process = _run_subprocess([*self.chroot_dnf_command,
            "--setopt", "protected_packages=", "--assumeno", "remove", *packages],
            expected_returncode = 1,
        )
        result: set[str] = set()
        for line in process.stdout.splitlines():
            if not line.startswith(" "):
                continue
            nvr = line.split()
            if len(nvr) != 6:
                continue
            result.add(f"{nvr[0]}-{nvr[2]}.{nvr[1]}")
        return result

    @traceLog()
    def get_buildrequires_providers(self, buildrequires: Iterable[str]) -> dict[str, list[str]]:
        """
        Get the mapping of BuildRequires fields to the RPMs that provide it.
        Each BR can be provided by multiple installed RPMs but we try to
        minimize it.
        """

        # Get both the mapping and the reverse mapping between each
        # BuildRequires field and the RPMs that provide it.
        br_providers: dict[str, list[str]] = {}
        provided_brs: dict[str, list[str]] = {}

        for br, process in zip(buildrequires, self.pool.map(lambda br: _run_subprocess(
            [*self.chroot_dnf_command, "repoquery", "--installed", "--whatprovides", br],
        ), buildrequires)):
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
    def check_removed_files(self, packages: Iterator[str]) -> Optional[str]:
        """
        Attempt to remove `packages` and check if any of the file owned by
        packages that would be removed, was accessed.
        """
        for path in self.get_files(self.try_remove(packages)):
            try:
                atime = self.accessed_files[self.buildroot.make_chroot_path(path)]
            except FileNotFoundError:
                continue
            if atime > self.min_time:
                for r in self.exclude_accessed_files:
                    if r.search(path) is not None:
                        break
                else:
                    return path
        return None

    @traceLog()
    def resolve_buildrequires(self) -> None:
        """
        Decide which BuildRequires fields were not used based on file accesses.
        """

        # First check each BuildRequires separately to quickly exclude most of
        # the candidates.
        candidates_providers: list[tuple[str, list[str]]] = []
        for (br, providers), path in zip(self.buildrequires_providers.items(),
            self.pool.map(self.check_removed_files, (
                providers for providers in self.buildrequires_providers.values()
            ))):
            if path is not None:
                getLog().info(
                    "unbreq plugin: BuildRequires '%s' is needed because file %s was accessed",
                    br, path
                )
            else:
                candidates_providers.append((br, providers))

        if len(candidates_providers) == 0:
            return

        # Check if all the providers can be removed together.
        if self.check_removed_files(p for _, ps in candidates_providers for p in ps) is not None:
            # Now execute the query with an increasing number of packages to be
            # certain that they all can be removed together.
            candidates_it = iter(candidates_providers)
            brs_can_be_removed: list[tuple[str, list[str]]] = [next(candidates_it)]
            for br, providers in candidates_it:
                path = self.check_removed_files((*(v for _, vs in brs_can_be_removed for v in vs), *providers))
                if path is not None:
                    getLog().info(
                        "unbreq plugin: BuildRequires '%s' is needed because file %s was accessed",
                        br, path
                    )
                else:
                    brs_can_be_removed.append((br, providers))

        for br, _ in candidates_providers:
            getLog().warning("unbreq plugin: BuildRequires '%s' was not used", br)

    @traceLog()
    def set_br_files_am_time(self) -> None:
        """
        Get all the BuildRequires, the RPMs that provide them, the files they
        own and set both their access and modify timestamps to zero.
        """
        def handle_file(path: str) -> None:
            try:
                os.utime(self.buildroot.make_chroot_path(path), (0, 0))
            except FileNotFoundError:
                pass

        all_files = self.get_files(self.try_remove(
            provider for providers in self.buildrequires_providers.values() for provider in providers
        ))

        for _ in self.pool.map(handle_file, all_files):
            pass

    @traceLog()
    def _EarlyPrebuildHook(self) -> None:
        """
        Initialize some chroot attributes.
        """

        if self.buildroot.pkg_manager.name == "dnf5":
            self.enabled = True
        elif self.buildroot.pkg_manager.name == "dnf4":
            self.enabled = True
            # DNF 4 can not be run concurrently
            self.pool = ThreadPoolExecutor(max_workers = 1)
        else:
            getLog().warning("unbreq plugin: '%s' package manager is not supported", self.buildroot.pkg_manager.name)

        if not self.enabled:
            return

        getLog().info("enabled unbreq plugin (earlyprebuild)")

        if self.buildroot.bootstrap_buildroot is not None:
            if USE_NSPAWN:
                # The `--ephemeral` flag is required in order to be able to run
                # `systemd-nspawn` concurrently.
                self.chroot_command = ["/usr/bin/systemd-nspawn", "--quiet", "--ephemeral", "--pipe",
                    "-D", self.buildroot.bootstrap_buildroot.rootdir, "--bind", self.buildroot.rootdir
                ]
            else:
                self.chroot_command = ["/usr/sbin/chroot", self.buildroot.bootstrap_buildroot.rootdir]
        self.chroot_rpm_command = [*self.chroot_command, "/usr/bin/rpm", "--root", self.buildroot.rootdir]
        self.chroot_dnf_command = [*self.chroot_command, self.buildroot.pkg_manager.command, "--installroot", self.buildroot.rootdir]

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
                if srpm.path not in self.srpms:
                    self.srpms.add(srpm.path)
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
            self.buildrequires_providers = self.get_buildrequires_providers(self.buildrequires_deptype.keys())

        # NOTE maybe find a better example file to touch to get an atime?
        path = self.buildroot.make_chroot_path("/dev/null")
        mockbuild.file_util.touch(path)
        self.min_time = os.path.getatime(path)

        mount_options_process = _run_subprocess(
            ["/usr/bin/findmnt", "-n", "-o", "OPTIONS", "--target", self.buildroot.rootdir],
        )
        self.mount_options = mount_options_process.stdout.rstrip().split(",")

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
