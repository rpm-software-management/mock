# -*- coding: utf-8 -*-
# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# License: GPL2 or later see COPYING

# python library imports
import codecs

# our imports
from mockbuild.trace_decorator import getLog, traceLog
import mockbuild.util

requires_api_version = "1.1"


# plugin entry point
@traceLog()
def init(plugins, conf, buildroot):
    HwInfo(plugins, conf, buildroot)


class HwInfo(object):
    # pylint: disable=too-few-public-methods
    """caches root environment in a tarball"""
    @traceLog()
    def __init__(self, plugins, conf, buildroot):
        self.buildroot = buildroot
        self.hw_info_opts = conf
        self.config = buildroot.config
        plugins.add_hook("preinit", self._PreInitHook)

    # =============
    # 'Private' API
    # =============
    @traceLog()
    def _unprivPreInitHook(self):
        getLog().info("enabled HW Info plugin")
        out_file = self.buildroot.resultdir + '/hw_info.log'
        out = codecs.open(out_file, 'w', 'utf-8', 'replace')

        cmd = ["/usr/bin/lscpu"]
        output = mockbuild.util.do(cmd, shell=False, returnOutput=True, raiseExc=False)
        out.write("CPU info:\n")
        out.write(output)

        cmd = ["/bin/free"]
        output = mockbuild.util.do(cmd, shell=False, returnOutput=True, raiseExc=False)
        out.write("\n\nMemory:\n")
        out.write(output)

        cmd = ["/bin/df", "-H", self.buildroot.make_chroot_path()]
        output = mockbuild.util.do(cmd, shell=False, returnOutput=True, raiseExc=False)
        out.write("\n\nStorage:\n")
        out.write(output)

        out.close()

    @traceLog()
    def _PreInitHook(self):
        with self.buildroot.uid_manager:
            self._unprivPreInitHook()
