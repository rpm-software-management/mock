# -*- coding: utf-8 -*-
# vim: noai:ts=4:sw=4:expandtab

from mockbuild.trace_decorator import getLog, traceLog
from mockbuild import util


class Tar:
    """ interacts with Tar and mask differences between gtar and bsdtar """

    @traceLog()
    def __init__(self, config):
        self.config = config

    def __repr__(self):
        return "Tar()".format()
