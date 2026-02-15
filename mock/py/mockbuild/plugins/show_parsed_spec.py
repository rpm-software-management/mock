# -*- coding: utf-8 -*-
# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# License: GPL2 or later see COPYING

# our imports
import os
from mockbuild.trace_decorator import getLog, traceLog
import mockbuild.util

requires_api_version = "1.1"


# plugin entry point
@traceLog()
def init(plugins, conf, buildroot):
    ShowParsedSpec(plugins, conf, buildroot)


class ShowParsedSpec(object):
    """Get the runtime rpmspec --parse"""
    # pylint: disable=too-few-public-methods
    @traceLog()
    def __init__(self, plugins, conf, buildroot):
        self.buildroot = buildroot
        self.opts = conf
        self.config = buildroot.config

        # actually run our plugin at this step
        plugins.add_hook("pre_srpm_build", self._PreBuildHook)

    @traceLog()
    def _PreBuildHook(self, host_chroot_spec, host_chroot_sources):
        getLog().info("enabled show_parsed_spec plugin")
        rootdir_prefix = self.buildroot.make_chroot_path()
        chroot_spec = host_chroot_spec.replace(rootdir_prefix, '')
        chroot_sources = host_chroot_sources.replace(rootdir_prefix, '')
        parsed_specfile = self.buildroot.resultdir + '/' + os.path.basename(chroot_spec)[:-4] + 'parsed.spec'

        cmd = ["/usr/bin/rpmspec", "--parse", chroot_spec] + self.opts.get("rpmspec_opts", [])
        output, _ = self.buildroot.doChrootPlugin(cmd, cwd=chroot_sources, returnOutput=True)
        with open(parsed_specfile, "w", encoding="utf-8") as o:
            o.write(output)

        self.buildroot.uid_manager.changeOwner(parsed_specfile, gid=self.config['chrootgid'])

