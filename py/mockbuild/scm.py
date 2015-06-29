# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# License: GPL2 or later see COPYING
# Written by Marko Myllynen
# Copyright (C) 2010 Marko Myllynen <myllynen@redhat.com>

import os
import pwd
import shlex
import shutil
import six
import subprocess
import sys
import tempfile

from .trace_decorator import traceLog
from . import util

# class
class scmWorker(object):
    """Build RPMs from SCM"""
    @traceLog()
    def __init__(self, log, opts, macros):
        self.log = log
        self.log.debug("Initializing SCM integration...")

        self.macros = macros

        self.method = opts['method']
        if self.method == "cvs":
            self.get = opts['cvs_get']
        elif self.method == "svn":
            self.get = opts['svn_get']
        elif self.method == "git":
            self.get = opts['git_get']
        else:
            self.log.error("Unsupported SCM method: " + self.method)
            sys.exit(5)

        self.branch = None
        self.postget = None
        if 'branch' in opts:
            self.branch = opts['branch']
        if self.branch:
            if self.method == "cvs":
                self.get = self.get.replace("SCM_BRN", "-r " + self.branch)
            elif self.method == "git":
                self.postget = "git checkout " + self.branch
            elif self.method == "svn":
                self.get = self.get.replace("SCM_BRN", self.branch)
            else:
                self.log.error("Unsupported SCM method: " + self.method)
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

        self.log.debug("SCM checkout command: " + self.get)
        self.log.debug("SCM checkout post command: " + str(self.postget))

    @traceLog()
    def get_sources(self):
        self.wrk_dir = tempfile.mkdtemp(".mock-scm." + self.pkg)
        self.src_dir = self.wrk_dir + "/" + self.pkg
        self.log.debug("SCM checkout directory: " + self.wrk_dir)
        util.do(shlex.split(self.get), shell=False, cwd=self.wrk_dir, env=os.environ)
        if self.postget:
            util.do(shlex.split(self.postget), shell=False, cwd=self.src_dir, env=os.environ)
        self.log.debug("Fetched sources from SCM")

    @traceLog()
    def adjust_git_timestamps(self):
        dir = util.pretty_getcwd()
        self.log.debug("Adjusting timestamps in " + self.src_dir)
        os.chdir(self.src_dir)
        proc = subprocess.Popen(['git', 'ls-files', '-z'], shell=False, stdout=subprocess.PIPE)
        for f in proc.communicate()[0].split('\0')[:-1]:
            rev = subprocess.Popen(['git', 'rev-list', 'HEAD', f], shell=False, stdout=subprocess.PIPE).stdout.readlines()[0].rstrip('\n')
            ts = subprocess.Popen(['git', 'show', '--pretty=format:%ai', '--abbrev-commit', rev, f], shell=False, stdout=subprocess.PIPE).stdout.readlines()[0].rstrip('\n')
            subprocess.Popen(['touch', '-d', ts, f], shell=False)
        os.chdir(dir)

    @traceLog()
    def prepare_sources(self):
        # import rpm after setarch
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
            self.log.error("Can't find spec file %s" % self.src_dir + "/" + self.spec)
            self.clean()
            sys.exit(5)
        self.spec = sf

       # Add passed RPM macros before parsing spec file
        for macro, expression in list(self.macros.items()):
            rpm.addMacro(macro.lstrip('%'), expression)

        # Dig out some basic information from the spec file
        self.sources = []
        self.name = self.version = None
        ts = rpm.ts()
        rpm_spec = ts.parseSpec(self.spec)
        self.name = rpm.expandMacro("%{name}")
        self.version = rpm.expandMacro("%{version}")
        tarball = None
        try:
            sources_list = rpm_spec.sources()
        except:
            sources_list = rpm_spec.sources
        for (filename, num, flags) in sources_list:
            self.sources.append(filename.split("/")[-1])
            if num == 0 and flags == 1:
                tarball = filename.split("/")[-1]
        self.log.debug("Sources: %s" % self.sources)

        # Adjust timestamps for Git checkouts
        if self.method == "git" and self.git_timestamps:
            self.adjust_git_timestamps()

        # Generate a tarball from the checked out sources if needed
        if str(self.write_tar).lower() == "true":
            tardir = self.name + "-" + self.version
            if tarball == None:
                tarball = tardir + ".tar.gz"
            taropts = ""

            # Always exclude vcs data from tarball unless told not to
            if str(self.exclude_vcs).lower() == "true":
                proc = subprocess.Popen(['tar', '--help'], shell=False, stdout=subprocess.PIPE)
                proc_result = proc.communicate()[0]
                if six.PY3:
                    proc_result = proc_result.decode()
                if "--exclude-vcs" in proc_result:
                    taropts = "--exclude-vcs"

            self.log.debug("Writing " + self.src_dir + "/" + tarball + "...")
            dir = os.getcwd()
            os.chdir(self.wrk_dir)
            os.rename(self.name, tardir)
            cmd = "tar caf " + tarball + " " + taropts + " " + tardir
            util.do(shlex.split(cmd), shell=False, cwd=self.wrk_dir, env=os.environ)
            os.rename(tarball, tardir + "/" + tarball)
            os.rename(tardir, self.name)
            os.chdir(dir)

        # Get possible external sources from an external sources directory
        for f in self.sources:
            if not os.path.exists(self.src_dir + "/" + f) and \
                   os.path.exists(self.ext_src_dir + "/" + f):
                self.log.debug("Copying " + self.ext_src_dir + "/" + f + " to " + self.src_dir + "/" + f)
                shutil.copy2(self.ext_src_dir + "/" + f, self.src_dir + "/" + f)

        self.log.debug("Prepared sources for building src.rpm")

        return (self.src_dir, self.spec)

    @traceLog()
    def clean(self):
        self.log.debug("Clean SCM checkout directory")
        util.rmtree(self.wrk_dir)
