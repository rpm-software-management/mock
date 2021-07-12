# -*- coding: utf-8 -*-
# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# License: GPL2 or later see COPYING
# Written by Marko Myllynen
# Copyright (C) 2010 Marko Myllynen <myllynen@redhat.com>

import os
import shlex
import shutil
import subprocess
import sys
import tempfile

from . import util
from . import file_util
from .trace_decorator import traceLog


class scmWorker(object):
    """Build RPMs from SCM"""
    @traceLog()
    def __init__(self, log, config_opts, macros):
        opts = config_opts['scm_opts']
        self.log = log
        self.log.debug("Initializing SCM integration...")

        self.name = self.version = None
        self.wrk_dir = self.src_dir = None
        self.sources = []
        self.macros = macros
        self.branch = None
        self.postget = []
        self.config = config_opts

        self.method = opts['method']
        if self.method == "cvs":
            self.get = opts['cvs_get']
        elif self.method == "svn":
            self.get = opts['svn_get']
        elif self.method == "git":
            self.get = opts['git_get']
        elif self.method == "distgit":
            self.get = opts['distgit_get']
            self.postget = [opts['distgit_src_get']]
        else:
            self.log.error("Unsupported SCM method: %s", self.method)
            sys.exit(5)

        if 'branch' in opts:
            self.branch = opts['branch']
        if self.branch:
            if self.method == "cvs":
                self.get = self.get.replace("SCM_BRN", "-r " + self.branch)
            elif self.method == "git":
                self.postget = ["git checkout " + self.branch]
                if "--recursive" in self.get or "--recurse-submodules" in self.get:
                    self.postget.append("git submodule update --init --recursive")
            elif self.method == "distgit":
                self.get = self.get.replace("SCM_BRN", self.branch)
            elif self.method == "svn":
                self.get = self.get.replace("SCM_BRN", self.branch)
            else:
                self.log.error("Unsupported SCM method: %s", self.method)
                sys.exit(5)
        elif self.method == "svn":
            self.get = self.get.replace("SCM_BRN", "trunk")
        self.get = self.get.replace("SCM_BRN", "")

        if 'package' in opts:
            self.pkg = opts['package']
        else:
            self.log.error("Trying to use SCM, package not defined")
            sys.exit(5)
        self.get = self.get.replace("SCM_PKG", self.pkg)

        self.spec = opts['spec']
        self.spec = self.spec.replace("SCM_PKG", self.pkg)

        self.ext_src_dir = opts['ext_src_dir']
        self.write_tar = opts['write_tar']
        self.exclude_vcs = opts['exclude_vcs']

        self.git_timestamps = opts['git_timestamps']

        self.log.debug("SCM checkout command: %s", self.get)
        for command in self.postget:
            self.log.debug("SCM checkout post command: %s", command)

    @traceLog()
    def get_sources(self):
        self.wrk_dir = tempfile.mkdtemp(".mock-scm." + os.path.basename(self.pkg))
        self.src_dir = self.wrk_dir + "/" + os.path.basename(self.pkg)
        self.log.debug("SCM checkout directory: %s", self.wrk_dir)
        try:
            util.do(shlex.split(self.get), shell=False, cwd=self.wrk_dir, env=os.environ)
        except PermissionError:
            self.log.error("{} does not exist or cannot be executed due permissions."
                           .format(shlex.split(self.get)[0]))
            sys.exit(5)

        for command in self.postget:
            try:
                util.do(shlex.split(command), shell=False, cwd=self.src_dir, env=os.environ)
            except PermissionError:
                self.log.error("{} does not exist or cannot be executed due permissions."
                               .format(shlex.split(command)[0]))
                sys.exit(5)

        self.log.debug("Fetched sources from SCM")

    @traceLog()
    def adjust_git_timestamps(self):
        cwd_dir = util.pretty_getcwd()
        self.log.debug("Adjusting timestamps in %s", self.src_dir)
        os.chdir(self.src_dir)
        proc = subprocess.Popen(['git', 'ls-files', '-z'], shell=False, stdout=subprocess.PIPE)
        for f in proc.communicate()[0].split('\0')[:-1]:
            rev = subprocess.Popen(
                ['git', 'rev-list', 'HEAD', f], shell=False, stdout=subprocess.PIPE
            ).stdout.readlines()[0].rstrip('\n')
            ts = subprocess.Popen(
                ['git', 'show', '--pretty=format:%ai', '--abbrev-commit', rev, f],
                shell=False, stdout=subprocess.PIPE
            ).stdout.readlines()[0].rstrip('\n')
            subprocess.Popen(['touch', '-d', ts, f], shell=False)
        os.chdir(cwd_dir)

    @traceLog()
    def prepare_sources(self):
        # import rpm after setarch
        # pylint: disable=import-outside-toplevel
        import rpm
        self.log.debug("Preparing SCM sources")

        # Check some helper files
        if os.path.exists(self.src_dir + "/.write_tar"):
            self.log.debug(".write_tar detected, will write tarball on the fly")
            self.write_tar = True

        # Figure out the spec file
        sf = self.src_dir + "/" + self.spec
        if not os.path.exists(sf):
            sf = self.src_dir + "/" + self.spec.lower()
        if not os.path.exists(sf):
            self.log.error("Can't find spec file %s/%s", self.src_dir, self.spec)
            self.clean()
            sys.exit(5)
        self.spec = sf

        # Add passed RPM macros before parsing spec file
        for macro, expression in list(self.macros.items()):
            # pylint: disable=no-member
            rpm.addMacro(macro.lstrip('%'), str(expression))

        # Dig out some basic information from the spec file
        self.sources = []
        ts = rpm.ts()
        # Spec might %include its sources
        # pylint: disable=no-member
        rpm.addMacro("_sourcedir", self.src_dir)
        rpm_spec = ts.parseSpec(self.spec)
        self.name = rpm.expandMacro("%{name}")
        self.version = rpm.expandMacro("%{version}")
        tarball = None
        for (filename, num, flags) in rpm_spec.sources:
            self.sources.append(filename.split("/")[-1])
            if num == 0 and flags == 1:
                tarball = filename.split("/")[-1]
        self.log.debug("Sources: %s", self.sources)

        # Adjust timestamps for Git checkouts
        if self.method == "git" and self.git_timestamps:
            self.adjust_git_timestamps()

        # Generate a tarball from the checked out sources if needed
        if str(self.write_tar).lower() == "true" and self.method != "distgit":
            tardir = self.name + "-" + self.version
            if tarball is None:
                tarball = tardir + ".tar.gz"
            taropts = ""

            if self.config["tar"] == "bsdtar":
                __tar_cmd = "bsdtar"
            else:
                __tar_cmd = "gtar"
            # Always exclude vcs data from tarball unless told not to
            if str(self.exclude_vcs).lower() == "true" and __tar_cmd == 'gtar':
                proc = subprocess.Popen(['tar', '--help'], shell=False, stdout=subprocess.PIPE)
                proc_result = proc.communicate()[0]
                proc_result = proc_result.decode()
                if "--exclude-vcs" in proc_result:
                    taropts = "--exclude-vcs"

            self.log.debug("Writing %s/%s...", self.src_dir, tarball)
            cwd_dir = os.getcwd()
            os.chdir(self.wrk_dir)
            os.rename(self.name, tardir)
            cmd = "{0} caf {1} {2} {3}".format(__tar_cmd, tarball, taropts, tardir)
            util.do(shlex.split(cmd), shell=False, cwd=self.wrk_dir, env=os.environ)
            os.rename(tarball, tardir + "/" + tarball)
            os.rename(tardir, self.name)
            os.chdir(cwd_dir)

        # Get possible external sources from an external sources directory
        for f in self.sources:
            if not os.path.exists(self.src_dir + "/" + f) and \
               os.path.exists(self.ext_src_dir + "/" + f):
                self.log.debug("Copying %s/%s to %s/%s", self.ext_src_dir, f, self.src_dir, f)
                shutil.copy2(self.ext_src_dir + "/" + f, self.src_dir + "/" + f)

        self.log.debug("Prepared sources for building src.rpm")

        return (self.src_dir, self.spec)

    @traceLog()
    def clean(self):
        self.log.debug("Clean SCM checkout directory")
        file_util.rmtree(self.wrk_dir)
