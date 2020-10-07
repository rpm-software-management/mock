# -*- coding: utf-8 -*-
# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:

from collections.abc import MutableMapping
import locale
import jinja2

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


# pylint: disable=no-member,unsupported-assignment-operation
class TemplatedDictionary(MutableMapping):
    """ Dictionary where __getitem__() is run through Jinja2 template """
    def __init__(self, *args, alias_spec=None, **kwargs):
        '''
        Use the object dict.

        Optional parameter 'alias_spec' is dictionary of form:
        {'aliased_to': ['alias_one', 'alias_two', ...], ...}
        When specified, and one of the aliases is accessed - the
        'aliased_to' config option is returned.
        '''
        self.__dict__.update(*args, **kwargs)

        self._aliases = {}
        if alias_spec:
            for aliased_to, aliases in alias_spec.items():
                for alias in aliases:
                    self._aliases[alias] = aliased_to

    # The next five methods are requirements of the ABC.
    def __setitem__(self, key, value):
        key = self._aliases.get(key, key)
        self.__dict__[key] = value

    def __getitem__(self, key):
        key = self._aliases.get(key, key)
        if '__jinja_expand' in self.__dict__ and self.__dict__['__jinja_expand']:
            return self.__render_value(self.__dict__[key])
        return self.__dict__[key]

    def __delitem__(self, key):
        del self.__dict__[key]

    def __iter__(self):
        return iter(self.__dict__)

    def __len__(self):
        return len(self.__dict__)

    # The final two methods aren't required, but nice to have
    def __str__(self):
        '''returns simple dict representation of the mapping'''
        return str(self.__dict__)

    def __repr__(self):
        '''echoes class, id, & reproducible representation in the REPL'''
        return '{}, TemplatedDictionary({})'.format(super(TemplatedDictionary, self).__repr__(),
                                                    self.__dict__)

    def copy(self):
        return TemplatedDictionary(self.__dict__)

    def __render_value(self, value):
        if isinstance(value, str):
            return self.__render_string(value)
        elif isinstance(value, list):
            # we cannot use list comprehension here, as we need to NOT modify the list (pointer to list)
            # and we need to modifiy only individual values in the list
            # If we would create new list, we cannot assign to it, which often happens in configs (e.g. plugins)
            for i in range(len(value)):  # pylint: disable=consider-using-enumerate
                value[i] = self.__render_value(value[i])
            return value
        elif isinstance(value, dict):
            # we cannot use list comprehension here, same reasoning as for `list` above
            for k in value.keys():
                value[k] = self.__render_value(value[k])
            return value
        else:
            return value

    def __render_string(self, value):
        orig = last = value
        max_recursion = self.__dict__.get('jinja_max_recursion', 5)
        for _ in range(max_recursion):
            template = jinja2.Template(value, keep_trailing_newline=True)
            value = _to_native(template.render(self.__dict__))
            if value == last:
                return value
            last = value
        raise ValueError("too deep jinja re-evaluation on '{}'".format(orig))


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
