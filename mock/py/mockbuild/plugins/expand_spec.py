"""A mock plugin to expand specfile in postdeps phase."""

# our imports
import os
from mockbuild.trace_decorator import getLog, traceLog

# pylint: disable=invalid-name
requires_api_version = "1.1"


# plugin entry point
@traceLog()
def init(plugins, conf, buildroot):
    """Register the expand_spec plugin with mock."""
    ExpandSpec(plugins, conf, buildroot)


class ExpandSpec:
    """Get the runtime rpmspec --parse"""
    # pylint: disable=too-few-public-methods
    @traceLog()
    def __init__(self, plugins, conf, buildroot):
        """Init the plugin."""
        self.buildroot = buildroot
        self.opts = conf
        self.config = buildroot.config
        self.logger = getLog()

        # actually run our plugin at this step
        plugins.add_hook("postdeps", self._postDepsHook)
        self.logger.info("expand_spec: initialized")

    @traceLog()
    def _postDepsHook(self):
        """postdeps hook to expand specfile by ``rpmspec --parse``."""
        self.logger.info("Executing expand_spec plugin")
        chroot_spec = self.buildroot.spec
        expanded_specfile = os.path.join(self.buildroot.resultdir, 'expanded-spec.txt')
        self.logger.info("Expanding original spec: %s to %s", chroot_spec, expanded_specfile)

        cmd = ["/usr/bin/rpmspec", "--parse", chroot_spec] + self.opts.get("rpmspec_opts", [])
        output, _ = self.buildroot.doChrootPlugin(cmd, returnOutput=True)
        with open(expanded_specfile, "w", encoding="utf-8") as o:
            o.write(output)

        self.buildroot.uid_manager.changeOwner(expanded_specfile, gid=self.config['chrootgid'])
        getLog().info("Expanded specfile written to: %s", expanded_specfile)
