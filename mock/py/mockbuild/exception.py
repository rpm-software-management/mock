# -*- coding: utf-8 -*-
# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# License: GPL2 or later see COPYING
# Originally written by Seth Vidal
# Sections taken from Mach by Thomas Vander Stichele
# Major reorganization and adaptation by Michael Brown
# Copyright (C) 2007 Michael E Brown <mebrown@michaels-house.net>
"""define most of the exceptions used."""

# classes


class Error(Exception):
    "base class for our errors."
    def __init__(self, msg, status=None):
        Exception.__init__(self)
        self.msg = msg
        self.resultcode = 1
        if status is not None:
            self.resultcode = status

    def __str__(self):
        return self.msg


# result/exit codes
# 0 = yay!
# 1 = something happened  - it's bad
# 2 = run without setuid wrapper
# 3 = invalid configuration
# 4 = only some packages were build during --chain
# 5 = cmdline processing error
# 6 = invalid architecture
# 10 = problem building the package
# 20 = error in the chroot of some kind
# 25 = LVM manipulation error
# 30 = Yum emitted an error of some sort
# 40 = some error in the pkg we're building
# 50 = error in mock command (varies for each command)
# 60 = buildroot locked
# 65 = LVM thinpool locked
# 70 = result dir could not be created
# 80 = unshare of namespace failed
# 110 = unbalanced call to state functions
# 120 = weak dependent package not installed

class BuildError(Error):
    "rpmbuild failed."
    def __init__(self, msg):
        Error.__init__(self, msg)
        self.msg = msg
        self.resultcode = 10


class RootError(Error):
    "failed to set up chroot"
    def __init__(self, msg):
        Error.__init__(self, msg)
        self.msg = msg
        self.resultcode = 20


class LvmError(Error):
    "LVM manipulation failed."
    def __init__(self, msg):
        Error.__init__(self, msg)
        self.msg = msg
        self.resultcode = 25


class YumError(RootError):
    "yum failed."
    def __init__(self, msg):
        RootError.__init__(self, msg)
        self.msg = msg
        self.resultcode = 30


class PkgError(Error):
    "error with the srpm given to us."
    def __init__(self, msg):
        Error.__init__(self, msg)
        self.msg = msg
        self.resultcode = 40


class BuildRootLocked(Error):
    "build root in use by another process."
    def __init__(self, msg):
        Error.__init__(self, msg)
        self.msg = msg
        self.resultcode = 60


class LvmLocked(Error):
    "LVM thinpool is locked."
    def __init__(self, msg):
        Error.__init__(self, msg)
        self.msg = msg
        self.resultcode = 65


class BadCmdline(Error):
    "user gave bad/inconsistent command line."
    def __init__(self, msg):
        Error.__init__(self, msg)
        self.msg = msg
        self.resultcode = 5


class InvalidArchitecture(Error):
    "invalid host/target architecture specified."
    def __init__(self, msg):
        Error.__init__(self, msg)
        self.msg = msg
        self.resultcode = 6


class ResultDirNotAccessible(Error):
    """
Could not create output directory for built rpms. The directory specified was:
    %s

Try using the --resultdir= option to select another location. Recommended location is --resultdir=~/mock/.
"""
    def __init__(self, msg):
        Error.__init__(self, msg)
        self.msg = msg
        self.resultcode = 70


class UnshareFailed(Error):
    "call to C library unshare(2) syscall failed"

    def __init__(self, msg):
        Error.__init__(self, msg)
        self.msg = msg
        self.resultcode = 80


class StateError(Error):
    "unbalanced call to state functions"

    def __init__(self, msg):
        Error.__init__(self, msg)
        self.msg = msg
        self.resultcode = 110


class ConfigError(Error):
    "invalid configuration"

    def __init__(self, msg):
        Error.__init__(self, msg)
        self.msg = msg
        self.resultcode = 3
