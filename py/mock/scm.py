# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# License: GPL2 or later see COPYING
# Written by Marko Myllynen
# Copyright (C) 2010 Marko Myllynen <myllynen@redhat.com>

# python library imports
import tempfile
import shutil
import shlex
import sys
import os

# our imports
from mock.trace_decorator import traceLog, decorate
import mock.util

# class
class scmWorker(object):
    """Build RPMs from SCM"""
    decorate(traceLog())
    def __init__(self, log, opts, selinux):
        self.log = log
        self.log.debug("Initializing SCM integration...")

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
        if 'branch' in opts:
            self.branch = opts['branch']
        if self.branch:
            if self.method == "cvs":
                self.get = self.get.replace("SCM_BRN", "-r " + self.branch)
            elif self.method == "git":
                self.get = self.get.replace("SCM_BRN", "-b " + self.branch)
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

        self.ext_src_dir = opts['ext_src_dir']
        self.write_tar = opts['write_tar']

        self.selinux = selinux

        self.log.debug("SCM checkout command: " + self.get)

    decorate(traceLog())
    def get_sources(self):
        self.wrk_dir = tempfile.mkdtemp(".mock-scm." + self.pkg)
        os.chmod(self.wrk_dir, 0755)
        self.src_dir = self.wrk_dir + "/" + self.pkg
        self.log.debug("SCM checkout directory: " + self.wrk_dir)
        mock.util.do(shlex.split(self.get), shell=False, cwd=self.wrk_dir)

        self.log.debug("Fetched sources from SCM")

    def prepare_sources(self):
        # import rpm after setarch
        import rpm
        self.log.debug("Preparing SCM sources")

        # Check some helper files
        if os.path.exists(self.src_dir + "/.write_tar"):
            self.log.debug(".write_tar detected, will write tarball on the fly")
            self.write_tar = True

        # Figure out the spec file
        self.spec = self.src_dir + "/" + self.pkg + ".spec"
        if not os.path.exists(self.spec):
            self.spec = self.src_dir + "/" + self.pkg.lower() + ".spec"
        if not os.path.exists(self.spec):
            self.log.error("Can't find spec file %s" % self.spec)
            sys.exit(5)

        # Dig out some basic information from the spec file
        self.sources = []
        self.name = self.version = None
        ts = rpm.ts()
        rpm_spec = ts.parseSpec(self.spec)
        self.name = rpm.expandMacro("%{name}")
        self.version = rpm.expandMacro("%{version}")
        for (filename, num, flags) in rpm_spec.sources:
            self.sources.append(filename.split("/")[-1])
        self.log.debug("Sources: %s" % self.sources)

        # Generate a tarball from the checked out sources if needed
        if self.write_tar:
            tardir = self.name + "-" + self.version
            tarball = tardir + ".tar.gz"
            self.log.debug("Writing " + self.src_dir + "/" + tarball + "...")
            if os.path.exists(self.src_dir + "/" + tarball):
                os.unlink(self.src_dir + "/" + tarball)
            open(self.src_dir + "/" + tarball, 'w').close()
            cmd = "tar czf " + self.src_dir + "/" + tarball + \
                  " --exclude " + self.src_dir + "/" + tarball + \
                  " --xform='s,^" + self.pkg + "," + tardir + ",' " + self.pkg
            mock.util.do(shlex.split(cmd), shell=False, cwd=self.wrk_dir)

        # Get possible external sources from EXT_SRC_DIR
        for f in self.sources:
            if not os.path.exists(self.src_dir + "/" + f) and \
                   os.path.exists(EXT_SRC_DIR + "/" + f):
                self.log.debug("Copying " + EXT_SRC_DIR + "/" + f + " to " + self.src_dir + "/" + f)
                shutil.copy2(EXT_SRC_DIR + "/" + f, self.src_dir + "/" + f)

        self.log.debug("Prepared sources for building src.rpm")

        return (self.src_dir, self.spec)

    decorate(traceLog())
    def clean(self):
        self.log.debug("Clean SCM checkout directory")
        mock.util.rmtree(self.wrk_dir, selinux=self.selinux)
