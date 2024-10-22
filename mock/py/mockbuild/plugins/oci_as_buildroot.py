"""
Generate OCI from prepared build chroot.
Use given OCI image as build chroot (TODO).
"""

import os
import mockbuild.util
from mockbuild.trace_decorator import getLog

requires_api_version = "1.1"


def init(plugins, conf, buildroot):
    """ The obligatory plugin entry point """
    OCIAsBuildroot(plugins, conf, buildroot)


class OCIAsBuildroot:
    """
    OCIAsBuildroot plugin (class).
    """
    def __init__(self, plugins, conf, buildroot):
        self.buildroot = buildroot
        self.state = buildroot.state
        self.conf = conf
        plugins.add_hook("postdeps", self.produce_buildroot_image)

    def do(self, cmd):
        """ Execute command on host (as root) """
        getLog().info("Executing %s", ' '.join(cmd))
        mockbuild.util.do(cmd)

    def _produce_image_as_root(self):
        name = f"mock-container-{self.buildroot.config['root']}"
        # TODO: chain build produces multiple buildroots
        tarball = os.path.join(self.buildroot.resultdir, "buildroot-oci.tar")
        chroot = self.buildroot.make_chroot_path()
        self.do(["buildah", "from", "--name", name, "scratch"])
        self.do(["buildah", "add", name, chroot, "/"])
        self.do(["buildah", "commit", "--format", "oci", name, "oci-archive:" +
                 tarball])
        self.do(["buildah", "rm", name])

    def produce_buildroot_image(self):
        """ Generate OCI image from buildroot using Buildah """
        try:
            self.state.start("producing buildroot as OCI image")
            with self.buildroot.uid_manager.elevated_privileges():
                self._produce_image_as_root()
        finally:
            self.state.finish("producing buildroot as OCI image")
