# -*- coding: utf-8 -*-
# vim: noai:ts=4:sw=4:expandtab

from .trace_decorator import getLog
from .exception import StateError


class State(object):
    def __init__(self):
        self._state = []
        # can be "unknown", "success" or "fail"
        self.result = "unknown"
        self.state_log = getLog("mockbuild.Root.state")

    def state(self):
        if not len(self._state):
            raise StateError("state called on empty state stack")
        return self._state[-1]

    def start(self, state):
        if state is None:
            raise StateError("start called with None State")
        self._state.append(state)
        self.state_log.info("Start: %s" % state)

    def finish(self, state):
        if len(self._state) == 0:
            raise StateError("finish called on empty state list")
        current = self._state.pop()
        if state != current:
            raise StateError("state finish mismatch: current: %s, state: %s" % (current, state))
        self.state_log.info("Finish: %s" % state)

    def alldone(self):
        if len(self._state) != 0:
            raise StateError("alldone called with pending states: %s" % ",".join(self._state))
