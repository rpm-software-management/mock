# -*- coding: utf-8 -*-
# vim: noai:ts=4:sw=4:expandtab

import hashlib
import json
import os
import logging
import subprocess
from contextlib import contextmanager

import backoff
from mockbuild.trace_decorator import getLog, traceLog


class PodmanError(Exception):
    """
    Exception raised by mockbuild.podman.Podman
    """


def podman_get_oci_digest(image, logger=None, podman_binary=None):
    """
    Get sha256 digest of RootFS layers. This must be identical for
    all images containing same order of layers, thus it can be used
    as the check that we've loaded same image.
    """
    logger = logger or logging.getLogger()
    podman = podman_binary or "/usr/bin/podman"
    logger.info("Calculating %s image OCI digest", image)
    check = [podman, "image", "inspect", image]
    result = subprocess.run(check, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, check=False,
                            encoding="utf8")
    if result.returncode:
        logger.error("Can't get %s podman image digest: %s", image, result.stderr)
        return None
    result = result.stdout.strip()

    try:
        data = json.loads(result)[0]
    except json.JSONDecodeError:
        logger.error("The manifest data of %s are not json-formatted.", image)
        return None

    if 'RootFS' not in data:
        logger.error("RootFS section of %s is missing.", image)
        return None
    if data['RootFS']['Type'] != 'layers':
        logger.error("Unexpected format for RootFS in %s.", image)
        return None

    # data which should be sufficient to confirm the image
    data = {
        'RootFS': data['RootFS'],
        'Config': data['Config'],
    }
    # convert to json string with ordered dicts and create hash
    data = json.dumps(data, sort_keys=True)
    return hashlib.sha256(data.encode()).hexdigest()


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
                         image_arch, system_arch)
            return False
    except subprocess.SubprocessError as exc:
        logger.error("Subprocess failed: %s", exc)
        return False

    return True


def pull_fail_handler(details):
    """
    Raise an error when image pull fails, because lambdas can't raise.
    """
    raise PodmanError("Image pull failed")


class Podman:
    """ interacts with podman to create build chroot """

    @traceLog()
    def __init__(self, buildroot, image):
        self.podman_binary = "/usr/bin/podman"
        if not os.path.exists(self.podman_binary):
            raise PodmanError(f"'{self.podman_binary}' not installed")

        self.buildroot = buildroot
        self.image = image
        self.image_id = None
        getLog().info("Using container image: %s", image)

    @traceLog()
    def pull_image(self):
        """ pull the latest image, return True if successful """
        logger = getLog()
        logger.info("Pulling image: %s", self.image)
        cmd = [self.podman_binary, "pull", self.image]

        res = subprocess.run(cmd, env=self.buildroot.env,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             check=False)
        if res.returncode != 0:
            logger.error("%s\n%s", res.stdout, res.stderr)
            return False

        # Record the image id for later use.  This is needed for the
        # oci-image:tarball images that not necessarily have tags/names.
        self.image_id = res.stdout.decode("utf-8").strip()
        return True

    @property
    def _tagged_id(self):
        uuid = self.buildroot.config["mock_run_uuid"]
        bootstrap = "-bootstrap" if self.buildroot.is_bootstrap else ""
        return f"mock{bootstrap}-{uuid}"

    def tag_image(self):
        """
        Tag the pulled image as mock-{uuid}, or mock-bootstrap-{uuid}.
        """
        if not self.image_id:
            raise PodmanError("No image to tag. Image pull failed or was not attempted")
        cmd = ["podman", "tag", self.image_id, self._tagged_id]
        getLog().info("Tagging container image as %s", self._tagged_id)
        subprocess.run(cmd, env=self.buildroot.env, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, check=True)

    def retry_image_pull(self, max_time):
        """ Try pulling the image multiple times """
        @backoff.on_predicate(backoff.expo, lambda x: not x,
                              max_time=max_time, jitter=backoff.full_jitter,
                              on_giveup=pull_fail_handler)
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
        cmd_mount = [self.podman_binary, "image", "mount", self.image_id]
        cmd_umount = [self.podman_binary, "image", "umount", self.image_id]
        result = subprocess.run(cmd_mount, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, check=False,
                                encoding="utf8")
        if result.returncode:
            message = "Podman mount failed: " + result.stderr
            raise PodmanError(message)

        mountpoint = result.stdout.strip()
        logger.info("mounting %s with podman image mount", self.image_id)
        try:
            logger.info("image %s as %s", self.image_id, mountpoint)
            yield mountpoint
        finally:
            logger.info("umounting image %s (%s) with podman image umount",
                        self.image_id, mountpoint)
            subprocess.run(cmd_umount, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, check=True)

    def get_oci_digest(self):
        """
        Get sha256 digest of RootFS layers. This must be identical for
        all images containing same order of layers, thus it can be used
        as the check that we've loaded same image.
        """
        the_image = self.image
        if the_image.startswith("oci-archive:"):
            # We can't query digest from tarball directly, but note
            # the image needs to be tagged first!
            the_image = self._tagged_id
        digest = podman_get_oci_digest(the_image, logger=getLog())
        if digest is None:
            raise PodmanError(f"Getting OCI digest for image {self.image} failed")
        return digest

    def check_native_image_architecture(self):
        """
        Check that self.image has been generated for the current
        host's architecture.
        """
        return podman_check_native_image_architecture(self.image_id, getLog())

    @traceLog()
    def cp(self, destination, tar_cmd):
        """ copy content of container to destination directory """
        getLog().info("Copy content of container %s to %s", self.image_id, destination)

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

    def untag(self):
        """
        Remove the additional image ID we created - which means the image itself
        is garbage-collected if there's no other tag.
        """
        cmd = ["podman", "rmi", self._tagged_id]
        getLog().info("Removing image %s", self._tagged_id)
        subprocess.run(cmd, env=self.buildroot.env, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, check=True)

    def read_image_id(self):
        """
        Given self.image (name), get the image Id.
        """
        cmd = ["podman", "image", "inspect", self.image, "--format",
               "{{ .Id }}"]
        getLog().info("Reading image .ID from %s", self.image)
        res = subprocess.run(cmd, env=self.buildroot.env,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             check=True)
        self.image_id = res.stdout.decode("utf-8").strip()


    def inspect_hermetic_metadata(self):
        """
        Get the image metadata needed for the subsequent hermetic build.
        """
        get_query = '{"pull_digest": "{{ .Digest }}", "id": "{{.Id}}", "architecture": "{{ .Architecture }}"}'
        getLog().info("Reading image %s from %s", get_query, self.image)
        cmd = ["podman", "image", "inspect", "--format", get_query, self.image]
        res = subprocess.run(cmd, env=self.buildroot.env,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             check=True)
        return json.loads(res.stdout.decode("utf-8").strip())


    def __repr__(self):
        return "Podman({}({}))".format(self.image, self.image_id)
