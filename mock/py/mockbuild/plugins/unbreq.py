#!/usr/bin/python3
# python library imports
import subprocess
import os
import re
from typing import (
    List,
)

# our imports
from mockbuild.trace_decorator import getLog, traceLog
import mockbuild.util
from mockbuild.util import USE_NSPAWN
import mockbuild.mounts

requires_api_version = "1.1"

class AtimeDict(dict):
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
        self.exclude_accessed_files = [re.compile(r) for r in self.config.get("plugin_conf", {}).get("unbreq_opts", {}).get("exclude_accessed_files", [])]
        self.accessed_files = AtimeDict()
        self.mount_options = None
        self.buildrequires = None

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
        process = subprocess.run(self.chroot_command + ["/usr/bin/rpm", "--root", self.buildroot.rootdir, "-q", "--qf", "[%{REQUIREFLAGS:deptype} %{REQUIRES} %{REQUIREFLAGS:depflags} %{REQUIREVERSION}\\n]", srpm],
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
        process = subprocess.run(self.chroot_command + ["/usr/bin/rpm", "--root", self.buildroot.rootdir, "-ql"] + packages,
            stdin = subprocess.DEVNULL, stdout = subprocess.PIPE, stderr = subprocess.PIPE, text = True
        )
        if process.returncode != 0:
            raise RuntimeError("process {} returned {}: {}".format(
                process.args, process.returncode, process.stderr.rstrip()
            ))
        else:
            return process.stdout.splitlines()
    
    @traceLog()
    def try_remove(self, packages: List[str]) -> List[str]:
        """
        Try to remove `packages` and obtain all the packages (NVRs) that would be removed.
        """
        process = subprocess.run(self.chroot_dnf_command + ["--setopt", "protected_packages=", "--assumeno", "remove"] + packages,
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
    def resolve_buildrequires(self):
        """
        Decide which BuildRequire fields were not used based on file accesses.
        """
        br_providers = dict()
        rev_br_providers = dict()
        for br in self.buildrequires:
            process = subprocess.run(
                self.chroot_dnf_command + ["repoquery", "--installed", "--whatprovides", br],
                stdin = subprocess.DEVNULL, stdout = subprocess.PIPE, stderr = subprocess.PIPE, text = True
            )
            if process.returncode != 0:
                raise RuntimeError("process {} returned {}: {}".format(
                    process.args, process.returncode, process.stderr.strip()
                ))
            br_providers_br = process.stdout.splitlines()
            br_providers[br] = br_providers_br
            for provider in br_providers_br:
                rev_br_providers.setdefault(provider, []).append(br)
        # attempt to resolve providers so that each BR is provided by only one provider
        sorted_br_providers = sorted(br_providers, key = lambda k: len(br_providers[k]))
        if len(sorted_br_providers) != 0 and len(sorted_br_providers[-1]) > 1:
            for br in sorted_br_providers:
                br_providers_br = br_providers[br]
                if len(br_providers_br) == 1:
                    for rev_br in rev_br_providers[br_providers_br[0]]:
                        if rev_br != br:
                            br_providers_rev_br = br_providers[rev_br]
                            if len(br_providers_rev_br) > 1:
                                try:
                                    br_providers_rev_br.remove(br_providers_br[0])
                                except ValueError:
                                    pass

################################################################################

        brs_can_be_removed = []
        for br, providers in br_providers.items():
            removed_packages = self.try_remove([v for vs in brs_can_be_removed for v in vs[1]] + providers)
            can_be_removed = True
            for path in self.get_files(removed_packages):
                path = self.buildroot.rootdir + path
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
                        getLog().info("unbreq plugin: cannot remove %s because file %s was accessed", br, short_path)
                        can_be_removed = False
                        break
            if can_be_removed:
                brs_can_be_removed.append((br, providers))
        if len(brs_can_be_removed) != 0:
            brs = list(map(lambda t: t[0], brs_can_be_removed))
            getLog().warning("unbreq plugin: the following BuildRequires were not used:\n\t%s", "\n\t".join(brs))

    @traceLog()
    def set_am_time(self):
        for filename in set(self.get_files(self.try_remove(self.buildrequires))):
            try:
                os.utime(self.buildroot.rootdir + filename, (0, 0))
            except FileNotFoundError:
                pass

    @traceLog()
    def _PreBuildHook(self):
        getLog().info("enabled unbreq plugin (prebuild)")
        
        if USE_NSPAWN:
            self.chroot_command = ["/usr/bin/systemd-nspawn", "--quiet", "--pipe", "-D", self.buildroot.bootstrap_buildroot.rootdir, "--bind", self.buildroot.rootdir]
        else:
            self.chroot_command = ["/usr/bin/chroot", self.buildroot.bootstrap_buildroot.rootdir]
        self.chroot_dnf_command = self.chroot_command + ["/usr/bin/dnf", "--installroot", self.buildroot.rootdir]
        self.srpm_dir = self.buildroot.rootdir + os.path.join(self.buildroot.builddir, "SRPMS")
        
        self.buildrequires = set()
        for srpm in os.scandir(self.srpm_dir):
            for br in self.do_with_chroot(lambda: self.get_buildrequires(srpm.path)):
                self.buildrequires.add(br)
        self.buildrequires = sorted(set(self.buildrequires))
        
        # NOTE maybe find a better example file to touch to get an atime?
        path = os.path.join(self.buildroot.rootdir, "dev", "null")
        subprocess.run(["touch", path], check = True)
        self.min_time = os.stat(path).st_atime
        
        try:
            mount_options_process = subprocess.run(["findmnt", "-n", "-o", "OPTIONS", "--target", self.buildroot.rootdir], stdin = subprocess.DEVNULL, stdout = subprocess.PIPE, stderr = subprocess.PIPE, text = True)
            if mount_options_process:
                self.mount_options = mount_options_process.stdout.rstrip().split(",")
        except FileNotFoundError:
            pass
        
        if "relatime" in self.mount_options:
            getLog().info("unbreq plugin: detected 'relatime' mount option, going to set access times of files under %s to 0", self.buildroot.rootdir)
            self.do_with_chroot(self.set_am_time)

    @traceLog()
    def _PostBuildHook(self):
        if self.buildroot.state.result != "success":
            return
        getLog().info("enabled unbreq plugin (postbuild)")

        if "noatime" in self.mount_options:
            getLog().warning("unbreq plugin: chroot %s is on a filesystem mounted with the 'noatime' option; detection will not work correctly, you may want to remount the proper directory with mount options 'strictatime,lazytime'", self.buildroot.rootdir)

        self.do_with_chroot(self.resolve_buildrequires)
