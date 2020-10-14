# -*- coding: utf-8 -*-
# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python
# License: GPL2 or later see COPYING
# Written by Michael Simacek
# Copyright (C) 2015 Red Hat, Inc.

import logging
import multiprocessing
import os
import shlex
import socket
import sys

from io import StringIO

from mockbuild import file_util
from mockbuild.exception import Error
from mockbuild.trace_decorator import traceLog

requires_api_version = "1.1"

RUNDIR = '/var/run/mock'
SOCKET_NAME = 'pm-request'
MAX_CONNECTIONS = 10


@traceLog()
def init(plugins, conf, buildroot):
    PMRequestPlugin(plugins, conf, buildroot)


class OutputFilter(object):
    @staticmethod
    def filter(record):
        return record.levelno == logging.DEBUG


class PMRequestPlugin(object):
    """
    Executes package manager commands requested by processes runninng in the
    chroot.
    """

    @traceLog()
    def __init__(self, plugins, conf, buildroot):
        self.buildroot = buildroot
        self.config = conf
        plugins.add_hook("earlyprebuild", self.start_listener)
        plugins.add_hook("preshell", self.start_listener)
        plugins.add_hook("postbuild", self.log_executed)

    @traceLog()
    def start_listener(self):
        process = multiprocessing.Process(
            name="pm-request-listener",
            target=lambda: PMRequestListener(self.config, self.buildroot).listen())
        process.daemon = True
        self.buildroot.env['PM_REQUEST_SOCKET'] = os.path.join(RUNDIR, SOCKET_NAME)
        self.buildroot.root_log.info("Enabled pm_request plugin")
        process.start()

    @traceLog()
    def log_executed(self):
        """ Obtains the list of executed commands from the daemon process """
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.connect(self.buildroot.make_chroot_path(RUNDIR, SOCKET_NAME))
            sock.sendall(b'!LOG_EXECUTED\n')
            executed_commands = sock.makefile().read()
            if executed_commands:
                self.buildroot.root_log.warning(
                    "The pm_request plugin executed following commands:\n"
                    + executed_commands
                    + "\nThe build may not be reproducible.\n")
        except socket.error:
            pass
        finally:
            sock.close()


class PMRequestListener(object):
    """ Daemon process that responds to requests """

    def __init__(self, config, buildroot):
        self.config = config
        self.buildroot = buildroot
        self.rundir = buildroot.make_chroot_path(RUNDIR)
        self.socket_path = os.path.join(self.rundir, SOCKET_NAME)
        self.executed_commands = []
        # util.do cannot return output when the command fails, we need to
        # capture it's logging
        self.log_buffer = StringIO()
        self.log = logging.getLogger("mockbuild.plugin.pm_request")
        self.log.level = logging.DEBUG
        self.log.addFilter(OutputFilter())
        self.log.propagate = False
        self.log.addHandler(logging.StreamHandler(self.log_buffer))

    def prepare_socket(self):
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.connect(self.socket_path)
        except (socket.error, OSError):
            try:
                os.unlink(self.socket_path)
            except OSError:
                pass
        else:
            # there's another process listening
            sys.exit(0)

        file_util.mkdirIfAbsent(self.rundir)
        # Don't allow regular users to access the socket as they may not be in
        # the mock group
        os.chown(self.rundir, self.buildroot.chrootuid, self.buildroot.chrootgid)
        os.chmod(self.rundir, 0o770)
        sock.bind(self.socket_path)
        os.chown(self.socket_path, self.buildroot.chrootuid, self.buildroot.chrootgid)
        return sock

    def listen(self):
        sock = self.prepare_socket()
        sock.listen(MAX_CONNECTIONS)
        while True:
            try:
                connection, _ = sock.accept()
                try:
                    line = connection.makefile().readline()
                    command = shlex.split(line)
                    # pylint:disable=E1101
                    if command == ["!LOG_EXECUTED"]:
                        connection.sendall('\n'.join(self.executed_commands).encode())
                    elif command:
                        success, out = self.execute_command(command)
                        connection.sendall(b"ok\n" if success else b"nok\n")
                        connection.sendall(out.encode())
                        if success:
                            self.executed_commands.append(line.strip())
                finally:
                    connection.close()
            except socket.error:
                continue

    def execute_command(self, command):
        try:
            self.buildroot.pkg_manager.execute(
                *command, printOutput=False, logger=self.log,
                returnOutput=False, pty=False, raiseExc=True)
            success = True
        except Error:
            success = False
        out = self.log_buffer.getvalue()
        self.log_buffer.seek(0)
        self.log_buffer.truncate()
        return success, out
