# -*- coding: utf-8 -*-
# vim: noai:ts=4:sw=4:expandtab

import subprocess
from contextlib import contextmanager

from mockbuild.trace_decorator import getLog, traceLog
from mockbuild import util
from mockbuild.exception import BootstrapError

class Podman:
    """ interacts with podman to create build chroot """

    @traceLog()
    def __init__(self, buildroot, image):
        self.buildroot = buildroot
        self.image = image
        self.container_id = None
        getLog().info("Using bootstrap image: %s", image)

    @traceLog()
    def pull_image(self):
        """ pull the latest image """
        logger = getLog()
        logger.info("Pulling image: %s", self.image)
        cmd = ["podman", "pull", self.image]
        out, exit_status = util.do_with_status(cmd, env=self.buildroot.env,
                                               raiseExc=False, returnOutput=1)
        if exit_status:
            logger.error(out)


    @contextmanager
    def mounted_image(self):
        """
        Using the "podman image mount" command, mount the image as a temporary
        read-only directory so we can copy-paste the contents into the final
        bootstrap chroot directory.
        """
        logger = getLog()
        cmd_mount = ["podman", "image", "mount", self.image]
        cmd_umount = ["podman", "image", "umount", self.image]
        result = subprocess.run(cmd_mount, capture_output=True, check=False, encoding="utf8")
        if result.returncode:
            message = "Podman mount failed: " + result.stderr
            raise BootstrapError(message)

        mountpoint = result.stdout.strip()
        logger.info("mounting %s with podman image mount", self.image)
        try:
            logger.info("image %s as %s", self.image, mountpoint)
            yield mountpoint
        finally:
            logger.info("umounting image %s (%s) with podman image umount",
                        self.image, mountpoint)
            subprocess.run(cmd_umount, check=True)

    @traceLog()
    def cp(self, destination, tar_cmd):
        """ copy content of container to destination directory """
        getLog().info("Copy content of container %s to %s", self.image, destination)
        with self.mounted_image() as mount_path:
            # pipe-out the temporary mountpoint with the help of tar utility
            cmd_podman = [tar_cmd, "-C", mount_path, "-c", "."]
            with subprocess.Popen(cmd_podman, stdout=subprocess.PIPE) as podman:
                # read the tarball from stdin, and extract to the destination
                # directory (bootstrap chroot directory)
                cmd_tar = [tar_cmd, "-xC", destination, "-f", "-"]
                with subprocess.Popen(cmd_tar, stdin=podman.stdout) as tar:
                    tar.communicate()
                    podman.communicate()

    def __repr__(self):
        return "Podman({}({}))".format(self.image, self.container_id)
