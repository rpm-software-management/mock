# -*- coding: utf-8 -*-
# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:

from .exception import ExternalDepsError
from .trace_decorator import traceLog


class ExternalDeps(object):
    """ Handles external dependecies. E.g external:* """

    def __init__(self, buildroot, bootstrap_buildroot, uid_manager):
        self.buildroot = buildroot
        self.bootstrap_buildroot = bootstrap_buildroot
        self.uid_manager = uid_manager

    # when python 3.9 becomes standard, this can be replaced by string.removeprefix()
    @classmethod
    def _remove_prefix(cls, intext, prefix):
        if intext.startswith(prefix):
            return intext[len(prefix):]
        return intext

    def extract_external_deps(self, requires):
        """ accepts list of (build)requires, returns all external deps """
        return [i for i in requires if i.startswith('external:')]

    @traceLog()
    def install_external_deps(self, deps):
        """Install dependencies using native library manager"""
        self.buildroot.root_log.info('Installing dependencies to satisfy external:*')

        prefix = 'external:pypi:'
        pypi_deps = [self._remove_prefix(i, prefix) for i in deps if i.startswith(prefix)]
        deps = [i for i in deps if not i.startswith(prefix)]
        if pypi_deps:
            self.install_external_deps_pypi(pypi_deps)

        prefix = 'external:crate:'
        crate_deps = [self._remove_prefix(i, prefix) for i in deps if i.startswith(prefix)]
        deps = [i for i in deps if not i.startswith(prefix)]
        if crate_deps:
            self.install_external_deps_crate(crate_deps)

        if deps:
            raise ExternalDepsError("Unknown external dependencies: {}".format(', '.join(deps)))

    @traceLog()
    def install_external_deps_pypi(self, deps):
        """ deps is list of python modules. Without the prefix. """
        self.bootstrap_buildroot.install_as_root('/usr/bin/pip3', 'python3-setuptools')
        command = [
            'pip3', "install",
            "--root", self.buildroot.make_chroot_path(),
            "--prefix", "/usr",
        ] + deps
        try:
            self.uid_manager.becomeUser(0, 0)
            self.buildroot.doOutChroot(command, shell=False, printOutput=True)
        except:  # pylint: disable=bare-except
            raise ExternalDepsError('Pip3 install failed')
        finally:
            self.uid_manager.restorePrivs()
        self.install_fake_rpm('pypi', deps)

    @traceLog()
    def install_external_deps_crate(self, deps):
        """ deps is list of Rust modules. Without the prefix. """
        self.bootstrap_buildroot.install_as_root('/usr/bin/cargo')
        command = ['cargo', "install", "--root", self.buildroot.make_chroot_path()] + deps
        try:
            self.uid_manager.becomeUser(0, 0)
            self.buildroot.doOutChroot(command, shell=False, printOutput=True)
        except:  # pylint: disable=bare-except
            raise ExternalDepsError('Cargo install failed')
        finally:
            self.uid_manager.restorePrivs()
        self.install_fake_rpm('crate', deps)

    @traceLog()
    def install_fake_rpm(self, external_type, deps):
        """ Create and install fake packages using create-fake-rpm """
        list_of_packages = []
        self.buildroot.install_as_root('create-fake-rpm')
        try:
            self.uid_manager.becomeUser(0, 0)
            for dep in deps:
                command = ['/usr/bin/create-fake-rpm', '--print-result',
                           '--build',
                           'external-{0}-{1}'.format(external_type, dep),
                           'external:{0}:{1}'.format(external_type, dep)]
                # The output here is:
                # Wrote: /fake-external-pypi-bokeh-0-0.noarch.rpm\n
                (output, _) = self.buildroot.doChroot(
                    command, returnOutput=True, returnStderr=False,
                    raiseExc=True)
                package = self.buildroot.make_chroot_path(output.split()[1])
                list_of_packages.append(package)
        finally:
            self.uid_manager.restorePrivs()
        self.buildroot.install_as_root(*list_of_packages)
