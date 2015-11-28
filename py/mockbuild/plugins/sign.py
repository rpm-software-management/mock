# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# License: GPL2 or later see COPYING
# Written by Julien BALLET <lta@fb.com>
# Copyright (C) 2014 Facebook

# python library imports
from mockbuild.trace_decorator import traceLog, getLog
from mockbuild.util import do, doshell, run
import glob
import os
import subprocess

requires_api_version = "1.1"


# plugin entry point
@traceLog()
def init(plugins, conf, buildroot):
    Sign(plugins, conf, buildroot)


class Sign(object):
    """Automatically sign package after build"""

    @traceLog()
    def __init__(self, plugins, conf, buildroot):
        self.plugins = plugins
        self.conf = conf
        self.buildroot = buildroot
        self.plugins.add_hook('postbuild', self.sign_results)

        getLog().info(conf)
        getLog().info("enabled package signing")

    def sign_results(self):
        rpms = glob.glob('%s/*.rpm' % self.buildroot.resultdir)
        if rpms:
            getLog().info("Signing %s", ', '.join(rpms))
            opts = self.conf['opts'] % {'rpms': ' '.join(rpms), 'resultdir': self.buildroot.resultdir}
            cmd = "{0} {1}".format(self.conf['cmd'], opts)
            getLog().info("Executing %s", cmd)
            self.buildroot.uid_manager.dropPrivsTemp()
            subprocess.call(cmd, shell=True, env=os.environ)
            self.buildroot.uid_manager.restorePrivs()
