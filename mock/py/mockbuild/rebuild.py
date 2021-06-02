# -*- coding: utf-8 -*-
# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# License: GPL2 or later see COPYING

import logging
import os.path
import sys
import time
from . import util
from .exception import BadCmdline
from .trace_decorator import traceLog

log = logging.getLogger()


@traceLog()
def rebuild_generic(items, commands, buildroot, config_opts, cmd, post=None, clean=True):
    start = time.time()
    try:
        for item in items:
            log.info("Start(%s)  Config(%s)", item, buildroot.shared_root_name)
            if clean:
                commands.clean()
            commands.init(prebuild=not config_opts.get('short_circuit'))
            ret = cmd(item)
            elapsed = time.time() - start
            log.info("Done(%s) Config(%s) %d minutes %d seconds",
                     item, config_opts['chroot_name'], elapsed // 60, elapsed % 60)
            log.info("Results and/or logs in: %s", buildroot.resultdir)
            commands.plugins.call_hooks("process_logs")

        if config_opts["cleanup_on_success"]:
            log.info("Cleaning up build root ('cleanup_on_success=True')")
            commands.clean()
        if post:
            post()
        return ret

    except (Exception, KeyboardInterrupt):
        elapsed = time.time() - start
        log.error("Exception(%s) Config(%s) %d minutes %d seconds",
                  item, buildroot.shared_root_name, elapsed // 60, elapsed % 60)
        log.info("Results and/or logs in: %s", buildroot.resultdir)
        commands.plugins.call_hooks("process_logs")
        if config_opts["cleanup_on_failure"]:
            log.info("Cleaning up build root ('cleanup_on_failure=True')")
            commands.clean()
        raise


@traceLog()
def do_rebuild(config_opts, commands, buildroot, options, srpms):
    "rebuilds a list of srpms using provided chroot"
    if len(srpms) < 1:
        log.critical("No package specified to rebuild command.")
        sys.exit(50)

    if len(srpms) > 1 and options.spec:
        log.critical("--spec argument only supported with single srpm.")
        sys.exit(50)

    util.checkSrpmHeaders(srpms)
    clean = config_opts['clean'] and not config_opts['scm']

    def build(srpm):
        commands.build(srpm, timeout=config_opts['rpmbuild_timeout'],
                       check=config_opts['check'], spec=options.spec)

    def post_build():
        if config_opts['post_install']:
            if buildroot.chroot_was_initialized:
                commands.install_build_results(commands.build_results)
            else:
                commands.init()
                commands.install_build_results(commands.build_results)
                if config_opts["cleanup_on_success"]:
                    log.info("Cleaning up build root ('cleanup_on_success=True')")
                    commands.clean()

        if config_opts["createrepo_on_rpms"]:
            log.info("Running createrepo on binary rpms in resultdir")
            with buildroot.uid_manager:
                util.createrepo(config_opts, buildroot.resultdir)

    rebuild_generic(srpms, commands, buildroot, config_opts, cmd=build,
                    post=post_build, clean=clean)


# pylint: disable=unused-argument
@traceLog()
def do_buildsrpm(config_opts, commands, buildroot, options, args):
    # verify the input command line arguments actually exist
    if not os.path.isfile(options.spec):
        raise BadCmdline("Input specfile does not exist: %s" % options.spec)
    if options.sources and not os.path.isdir(options.sources) and not os.path.isfile(options.sources):
        raise BadCmdline("Input sources directory or file does not exist: %s" % options.sources)
    clean = config_opts['clean']

    def cmd(spec):
        return commands.buildsrpm(spec=spec, sources=options.sources,
                                  timeout=config_opts['rpmbuild_timeout'],
                                  follow_links=options.symlink_dereference)

    return rebuild_generic([options.spec], commands, buildroot, config_opts,
                           cmd=cmd, post=None, clean=clean)
