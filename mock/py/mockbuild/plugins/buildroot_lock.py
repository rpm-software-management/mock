"""
Produce a lockfile for the prepared buildroot by Mock.  Once available, we
should use the DNF built-in command from DNF5:
https://github.com/rpm-software-management/dnf5/issues/833
"""

import json
import os

from mockbuild.podman import Podman
from mockbuild.installed_packages import query_packages, query_packages_location

requires_api_version = "1.1"


def init(plugins, conf, buildroot):
    """ The obligatory plugin entry point """
    BuildrootLockfile(plugins, conf, buildroot)


class BuildrootLockfile:
    """ Produces buildroot_lock.json file in resultdir """
    def __init__(self, plugins, conf, buildroot):
        self.buildroot = buildroot
        self.state = buildroot.state
        self.conf = conf
        self.inst_done = False
        plugins.add_hook("postdeps", self.produce_lockfile)

    def produce_lockfile(self):
        """
        Upon a request ('produce_lockfile' option set True), generate
        the mock-build-environment.json file in resultdir.  The file describes
        the Mock build environment, and the way to reproduce it.
        """

        filename = "buildroot_lock.json"
        statename = "Generating the buildroot lockfile: " + filename
        try:
            with self.buildroot.uid_manager:
                self.state.start(statename)
                out_file = os.path.join(self.buildroot.resultdir, filename)
                chrootpath = self.buildroot.make_chroot_path()

                # Ḿimic the Koji Content Generator metadata fields:
                # https://docs.pagure.org/koji/content_generator_metadata/#buildroots
                #
                # The query_packages() method below sorts its output according
                # to _values_ of the queried RPM headers, so keep name-arch pair
                # first to have the output sorted reasonably.
                query_fields = ["name", "arch", "license", "version", "release",
                                "epoch", "sigmd5", "signature"]

                def _executor(cmd):
                    out, _ = self.buildroot.doOutChroot(cmd, returnOutput=True,
                                                        returnStderr=False)
                    return out

                packages = query_packages(query_fields, chrootpath, _executor)
                query_packages_location(packages, chrootpath, _executor)

                data = {
                    # Try to semver.  The future Mock versions (the tool) should
                    # be able to read older Minor versions of the same Major.
                    # Anytime we break this assumption, bump the Major.  IOW,
                    # the latest Mock implementing with Major == 1 can read any
                    # version from the 1.Y.Z range.  Mock implementing v2.Y.Z
                    # no longer reads v1.Y.Z variants.
                    "version": "1.0.0",
                    "buildroot": {
                        "rpms": packages,
                    },
                    # Try to keep this as minimal as possible.  If possible,
                    # implement the config options as DEFAULTS in the
                    # isolated-build.cfg, or in the
                    # process_isolated_build_config() method.
                    "config": {}
                }
                for cfg_option in [
                    # These are hard-coded in the configuration file, but we
                    # work with a single-config-for-all-arches now.
                    "target_arch",
                    "legal_host_arches",
                    "dist",
                    "package_manager",
                    # At this point, we only support isolated builds iff
                    # bootstrap_image_ready=True, so these two options are
                    # useful for implementing "assertion" in the
                    # process_isolated_build_config() method.
                    "bootstrap_image",
                    "bootstrap_image_ready",
                    # Macros need to be inherited, e.g., to keep the original
                    # %vendor tag specification, or %_host_cpu hacks.
                    "macros",
                ]:
                    if cfg_option in self.buildroot.config:
                        data["config"][cfg_option] = self.buildroot.config[cfg_option]

                if "bootstrap_image" in data["config"]:
                    # Optional object, only if bootstrap image used (we still
                    # produce lockfiles even if these are useless for isolated
                    # builds).
                    with self.buildroot.uid_manager.elevated_privileges():
                        podman = Podman(self.buildroot,
                                        data["config"]["bootstrap_image"])
                        digest = podman.get_image_digest()
                    data["bootstrap"] = {
                        "image_digest": digest,
                    }

                with open(out_file, "w", encoding="utf-8") as fdlist:
                    fdlist.write(json.dumps(data, indent=4, sort_keys=True) + "\n")
        finally:
            self.state.finish(statename)
