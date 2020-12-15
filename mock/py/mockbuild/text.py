# -*- coding: utf-8 -*-
# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:

import locale

from .trace_decorator import getLog

encoding = locale.getpreferredencoding()


def compat_expand_string(string, conf_dict):
    """
    Expand %(uid)s, etc., only if needed - and warn the user
    that Jinja should be used instead.
    """
    if '%(' not in string:
        return string
    getLog().warning("Obsoleted %(foo) config expansion in '{}', "
                     "use Jinja alternative {{foo}}".format(string))
    return string % conf_dict


def _to_text(obj, arg_encoding='utf-8', errors='strict', nonstring='strict'):
    if isinstance(obj, str):
        return obj
    elif isinstance(obj, bytes):
        return obj.decode(arg_encoding, errors)
    else:
        if nonstring == 'strict':
            raise TypeError('First argument must be a string')
        raise ValueError('nonstring must be one of: ["strict",]')


_to_native = _to_text
