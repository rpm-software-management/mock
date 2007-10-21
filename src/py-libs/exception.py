# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# License: GPL2 or later see COPYING
# Originally written by Seth Vidal
# Sections taken from Mach by Thomas Vander Stichele
# Major reorganization and adaptation by Michael Brown
# Copyright (C) 2007 Michael E Brown <mebrown@michaels-house.net>

# python library imports
from exceptions import Exception

# our imports

# classes
class Error(Exception):
    def __init__(self, msg):
        Exception.__init__(self)
        self.msg = msg
        self.resultcode = 1

    def __str__(self):
        return self.msg

# result/exit codes
# 0 = yay!
# 1 = something happened  - it's bad
# 5 = cmdline processing error
# 10 = problem building the package
# 20 = error in the chroot of some kind
# 30 = Yum emitted an error of some sort
# 40 = some error in the pkg we're building
# 50 = tried to fork a subcommand and it errored out
# 60 = buildroot locked

class BuildError(Error):
    def __init__(self, msg):
        Error.__init__(self, msg)
        self.msg = msg
        self.resultcode = 10

class RootError(Error):
    def __init__(self, msg):
        Error.__init__(self, msg)
        self.msg = msg
        self.resultcode = 20

class YumError(Error): 
    def __init__(self, msg):
        Error.__init__(self, msg)
        self.msg = msg
        self.resultcode = 30

class PkgError(Error):
    def __init__(self, msg):
        Error.__init__(self, msg)
        self.msg = msg
        self.resultcode = 40

class BuildRootLocked(Error):
    def __init__(self, msg):
        Error.__init__(self, msg)
        self.msg = msg
        self.resultcode = 60

class BadCmdline(Error):
    def __init__(self, msg):
        Error.__init__(self, msg)
        self.msg = msg
        self.resultcode = 05
