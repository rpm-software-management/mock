# -*- coding: utf-8 -*-
# vim: noai:ts=4:sw=4:expandtab

import subprocess
from mockbuild.trace_decorator import getLog, traceLog
from mockbuild import util

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
        getLog().info("Pulling image: %s", self.image)
        cmd = ["podman", "pull", self.image]
        util.do(cmd, printOutput=True)

    @traceLog()
    def get_container_id(self):
        """ start a container and detach immediately """
        cmd = ["podman", "run", "-it", "--detach", self.image, "/bin/bash"]
        container_id = util.do(cmd, returnOutput=True)
        self.container_id = container_id.strip()

    @traceLog()
    def exec(self, command):
        """ make sure the image contains expected packages """
        cmd = ["podman", "exec", self.container_id] + command
        util.do(cmd, printOutput=True)

    @traceLog()
    def export(self, cache_file_name, compress_program):
        """ export container and compress it  """
        getLog().info("Exporting container: %s as %s", self.image, cache_file_name)
        cmd_podman = ["podman", "export", self.container_id]
        podman = subprocess.Popen(cmd_podman, stdout=subprocess.PIPE)
        cache_file = open(cache_file_name, "w")
        cmd_compressor = [compress_program, "--stdout"]
        compressor = subprocess.Popen(cmd_compressor, stdin=podman.stdout, stdout=cache_file)
        compressor.communicate()
        podman.communicate()
        cache_file.close()

    @traceLog()
    def cp(self, destination, tar_cmd):
        """ copy content of container to destination directory """
        getLog().info("Copy content of container %s to %s", self.image, destination)
        cmd_podman = ["podman", "export", self.container_id]
        podman = subprocess.Popen(cmd_podman, stdout=subprocess.PIPE)
        cmd_tar = [tar_cmd, "-xC", destination]
        tar = subprocess.Popen(cmd_tar, stdin=podman.stdout)
        tar.communicate()
        podman.communicate()

    @traceLog()
    def remove(self):
        """ remove the container """
        cmd = ["podman", "rm", "-f", self.container_id]
        util.do(cmd)
        self.container_id = None

    def __repr__(self):
        return "Podman({}({}))".format(self.image, self.container_id)
