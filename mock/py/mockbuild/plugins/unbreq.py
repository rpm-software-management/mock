#!/usr/bin/python3
# python library imports
import subprocess
import os
import re
from typing import (
    Dict,
    List,
)

# our imports
from mockbuild.trace_decorator import getLog, traceLog
import mockbuild.util
from mockbuild.util import USE_NSPAWN
import mockbuild.mounts

requires_api_version = "1.1"

class AtimeDict(dict):
    """
    A caching lazy dictionary mapping file paths to their access time.
    """

    def __missing__(self, key):
        result = os.stat(key).st_atime
        self[key] = result
        return result

# plugin entry point
@traceLog()
def init(plugins, conf, buildroot):
    Unbreq(plugins, conf, buildroot)

class Unbreq(object):
    @traceLog()
    def __init__(self, plugins, conf, buildroot):
        self.buildroot = buildroot
        self.showrc_opts = conf
        self.config = buildroot.config

        self.min_time = None
        self.exclude_accessed_files = [re.compile(r) for r in
            self.config.get("plugin_conf", {}).get("unbreq_opts", {}).get("exclude_accessed_files", [])
        ]
        self.accessed_files = AtimeDict()
        self.mount_options = None
        self.buildrequires_providers = None

        # TODO handle different package managers
        # self.buildroot.pkg_manager.name

        plugins.add_hook("prebuild", self._PreBuildHook)
        plugins.add_hook("postbuild", self._PostBuildHook)

    @traceLog()
    def do_with_chroot(self, function):
        if USE_NSPAWN:
            return function()
        else:
            with mockbuild.mounts.BindMountPoint(self.buildroot.rootdir,
                self.buildroot.bootstrap_buildroot.make_chroot_path(self.buildroot.rootdir)).having_mounted():
                return function()

    @traceLog()
    def get_buildrequires(self, srpm: str) -> List[str]:
        """
        Get the BuildRequires fields of a SRPM file.
        """
        process = subprocess.run(self.chroot_command + ["/usr/bin/rpm", "--root", self.buildroot.rootdir, "-q",
            "--qf", "[%{REQUIREFLAGS:deptype} %{REQUIRES} %{REQUIREFLAGS:depflags} %{REQUIREVERSION}\\n]", srpm],
            stdin = subprocess.DEVNULL, stdout = subprocess.PIPE, stderr = subprocess.PIPE, text = True
        )
        if process.returncode != 0:
            raise RuntimeError("process {} returned {}: {}".format(
                process.args, process.returncode, process.stderr.rstrip()
            ))
        result = []
        for line in process.stdout.splitlines():
            if line.startswith("manual "):
                result.append(line[7:].rstrip())
        return result

    @traceLog()
    def get_files(self, packages: List[str]) -> List[str]:
        """
        Get the files owned by `packages` using an RPM query.
        """
        if len(packages) == 0:
            return []
        process = subprocess.run(self.chroot_command +
            ["/usr/bin/rpm", "--root", self.buildroot.rootdir, "-q", "--qf", "[%{FILENAMES}\\n]"] + packages,
            stdin = subprocess.DEVNULL, stdout = subprocess.PIPE, stderr = subprocess.PIPE, text = True,
        )
        if process.returncode != 0:
            raise RuntimeError("process {} returned {}: {}".format(
                process.args, process.returncode, process.stderr.rstrip()
            ))
        result = process.stdout.splitlines()
        return result

    @traceLog()
    def try_remove(self, packages: List[str]) -> List[str]:
        """
        Try to remove `packages` and obtain all the packages (NVRs) that would be removed.
        """
        process = subprocess.run(self.chroot_dnf_command +
            ["--setopt", "protected_packages=", "--assumeno", "remove"] + packages,
            stdin = subprocess.DEVNULL, stdout = subprocess.PIPE, stderr = subprocess.PIPE, text = True,
        )
        if process.returncode != 1:
            raise RuntimeError("process {} returned {}: {}".format(
                process.args, process.returncode, process.stderr.rstrip()
            ))
        result = []
        for line in process.stdout.splitlines():
            if not line.startswith(" "):
                continue
            nvr = line.split()
            if len(nvr) != 6:
                continue
            result.append("{}-{}.{}".format(nvr[0], nvr[2], nvr[1]))
        return result

    @traceLog()
    def get_buildrequires_providers(self, buildrequires: List[str]) -> Dict[str, List[str]]:
        """
        Get the mapping of BuildRequires fields to the RPMs that provide it.
        Each BR can be provided by multiple installed RPMs but we try to
        minimize it.
        """

        # Get both the mapping and the reverse mapping between each BuildRequire
        # and the RPMs that provide it.
        br_providers: Dict[str, List[str]] = dict()
        provided_brs: Dict[str, List[str]] = dict()
        for br in buildrequires:
            process = subprocess.run(
                self.chroot_dnf_command + ["repoquery", "--installed", "--whatprovides", br],
                stdin = subprocess.DEVNULL, stdout = subprocess.PIPE, stderr = subprocess.PIPE, text = True
            )
            if process.returncode != 0:
                raise RuntimeError("process {} returned {}: {}".format(
                    process.args, process.returncode, process.stderr.strip()
                ))
            current_br_providers: List[str] = process.stdout.splitlines()
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
    def resolve_buildrequires(self):
        """
        Decide which BuildRequire fields were not used based on file accesses.
        """
        brs_can_be_removed = []
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
                    skip = False
                    for r in self.exclude_accessed_files:
                        if r.search(short_path) is not None:
                            skip = True
                            break
                    else:
                        getLog().info(
                            "unbreq plugin: BuildRequire %s is needed because file %s was accessed",
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
    def set_br_files_am_time(self):
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
    def _PreBuildHook(self):
        getLog().info("enabled unbreq plugin (prebuild)")

        if USE_NSPAWN:
            self.chroot_command = ["/usr/bin/systemd-nspawn", "--quiet", "--pipe",
                "-D", self.buildroot.bootstrap_buildroot.rootdir, "--bind", self.buildroot.rootdir
            ]
        else:
            self.chroot_command = ["/usr/bin/chroot", self.buildroot.bootstrap_buildroot.rootdir]
        self.chroot_dnf_command = self.chroot_command + ["/usr/bin/dnf", "--installroot", self.buildroot.rootdir]
        self.srpm_dir = self.buildroot.make_chroot_path(self.buildroot.builddir, "SRPMS")

        buildrequires = set()
        for srpm in os.scandir(self.srpm_dir):
            for br in self.do_with_chroot(lambda: self.get_buildrequires(srpm.path)):
                buildrequires.add(br)
        self.buildrequires_providers = self.get_buildrequires_providers(sorted(buildrequires))

        # NOTE maybe find a better example file to touch to get an atime?
        path = os.path.join(self.buildroot.rootdir, "dev", "null")
        subprocess.run(["touch", path], check = True)
        self.min_time = os.stat(path).st_atime

        try:
            mount_options_process = subprocess.run(
                ["findmnt", "-n", "-o", "OPTIONS", "--target", self.buildroot.rootdir],
                stdin = subprocess.DEVNULL, stdout = subprocess.PIPE, stderr = subprocess.PIPE, text = True,
            )
            if mount_options_process:
                self.mount_options = mount_options_process.stdout.rstrip().split(",")
        except FileNotFoundError:
            pass

        if "relatime" in self.mount_options:
            getLog().info(
                "unbreq plugin: detected 'relatime' mount option, going to set access times of files under %s to 0",
                self.buildroot.rootdir
            )
            self.do_with_chroot(self.set_br_files_am_time)

    @traceLog()
    def _PostBuildHook(self):
        if self.buildroot.state.result != "success":
            return
        getLog().info("enabled unbreq plugin (postbuild)")

        if "noatime" in self.mount_options:
            getLog().warning(
                "unbreq plugin: chroot %s is on a filesystem mounted with the 'noatime' option;"
                "detection will not work correctly,"
                "you may want to remount the proper directory with mount options 'strictatime,lazytime'",
                self.buildroot.rootdir
            )

        self.do_with_chroot(self.resolve_buildrequires)
