# -*- coding: utf-8 -*-
# vim: noai:ts=4:sw=4:expandtab

import os
import logging
import subprocess
from contextlib import contextmanager

import backoff
from mockbuild.trace_decorator import getLog, traceLog
from mockbuild import util


class PodmanError(Exception):
    """
    Exception raised by mockbuild.podman.Podman
    """


def podman_check_native_image_architecture(image, logger=None, podman_binary=None):
    """
    Return True if image's architecture is "native" for this host.
    Relates:
        https://github.com/containers/podman/issues/19717
        https://github.com/fedora-copr/copr/issues/2875
    """

    logger = logger or logging.getLogger()
    podman = podman_binary or "/usr/bin/podman"
    logger.info("Checking that %s image matches host's architecture", image)
    sys_check_cmd = [podman, "version", "--format", "{{.OsArch}}"]
    image_check_cmd = [podman, "image", "inspect",
                       "--format", "{{.Os}}/{{.Architecture}}", image]

    def _podman_query(cmd):
        return subprocess.check_output(cmd, encoding="utf8").strip()

    try:
        system_arch = _podman_query(sys_check_cmd)
        image_arch = _podman_query(image_check_cmd)
        if system_arch != image_arch:
            logger.error("Image architecture %s doesn't match system arch %s",
                         system_arch, image_arch)
            return False
    except subprocess.SubprocessError as exc:
        logger.error("Subprocess failed: %s", exc)
        return False

    return True


class Podman:
    """ interacts with podman to create build chroot """

    @traceLog()
    def __init__(self, buildroot, image):
        self.podman_binary = "/usr/bin/podman"
        if not os.path.exists(self.podman_binary):
            raise PodmanError(f"'{self.podman_binary}' not installed")

        self.buildroot = buildroot
        self.image = image
        self.container_id = None
        getLog().info("Using container image: %s", image)

    @traceLog()
    def pull_image(self):
        """ pull the latest image, return True if successful """
        logger = getLog()
        logger.info("Pulling image: %s", self.image)
        cmd = [self.podman_binary, "pull", self.image]
        out, exit_status = util.do_with_status(cmd, env=self.buildroot.env,
                                               raiseExc=False, returnOutput=1)
        if exit_status:
            logger.error(out)
        return not exit_status

    def import_tarball(self, tarball):
        """
        Import tarball using podman into the local database.
        """
        getLog().info("Loading container image from %s", tarball)
        cmd = [self.podman_binary, "load", "-i", tarball]
        util.do_with_status(cmd, env=self.buildroot.env)

    def retry_image_pull(self, max_time):
        """ Try pulling the image multiple times """
        @backoff.on_predicate(backoff.expo, lambda x: not x,
                              max_time=max_time, jitter=backoff.full_jitter)
        def _keep_trying():
            return self.pull_image()
        _keep_trying()

    @contextmanager
    def mounted_image(self):
        """
        Using the "podman image mount" command, mount the image as a temporary
        read-only directory so we can copy-paste the contents into the final
        chroot directory.
        """
        logger = getLog()
        cmd_mount = [self.podman_binary, "image", "mount", self.image]
        cmd_umount = [self.podman_binary, "image", "umount", self.image]
        result = subprocess.run(cmd_mount, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, check=False,
                                encoding="utf8")
        if result.returncode:
            message = "Podman mount failed: " + result.stderr
            raise PodmanError(message)

        mountpoint = result.stdout.strip()
        logger.info("mounting %s with podman image mount", self.image)
        try:
            logger.info("image %s as %s", self.image, mountpoint)
            yield mountpoint
        finally:
            logger.info("umounting image %s (%s) with podman image umount",
                        self.image, mountpoint)
            subprocess.run(cmd_umount, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, check=True)

    def get_image_digest(self):
        """
        Get the "sha256:..." string for the image we work with.
        """
        check = [self.podman_binary, "image", "inspect", self.image,
                 "--format", "{{ .Digest }}"]
        result = subprocess.run(check, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, check=False,
                                encoding="utf8")
        if result.returncode:
            raise PodmanError(f"Can't get {self.image} podman image digest: {result.stderr}")
        result = result.stdout.strip()
        if len(result.splitlines()) != 1:
            raise PodmanError(f"The digest of {self.image} image is not a single-line string")
        return result

    def check_native_image_architecture(self):
        """
        Check that self.image has been generated for the current
        host's architecture.
        """
        return podman_check_native_image_architecture(self.image, getLog())

    @traceLog()
    def cp(self, destination, tar_cmd):
        """ copy content of container to destination directory """
        getLog().info("Copy content of container %s to %s", self.image, destination)

        with self.mounted_image() as mount_path:
            # pipe-out the temporary mountpoint with the help of tar utility
            cmd_podman = [tar_cmd, "-C", mount_path, "-c", "."]
            with subprocess.Popen(cmd_podman, stdout=subprocess.PIPE) as podman:
                # read the tarball from stdin, and extract to the destination
                # directory (chroot directory)
                cmd_tar = [tar_cmd, "-xC", destination, "-f", "-"]
                with subprocess.Popen(cmd_tar, stdin=podman.stdout) as tar:
                    tar.communicate()
                    podman.communicate()

    def __repr__(self):
        return "Podman({}({}))".format(self.image, self.container_id)
