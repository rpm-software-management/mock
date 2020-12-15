import pytest
from templated_dictionary import TemplatedDictionary


def test_transitive_expand():
    config = TemplatedDictionary()
    config['a'] = 'test'
    config['b'] = '{{ a }} {{ a }}'
    config['c'] = '{{ b + " " + b }}'
    assert config['c'] == '{{ b + " " + b }}'
    config['__jinja_expand'] = True
    assert config['c'] == 'test test test test'


def test_aliases():
    config = TemplatedDictionary(
        alias_spec={
            'dnf.conf': ['yum.conf', 'package_manager.conf'],
        },
    )

    config['dnf.conf'] = "initial"
    config['yum.conf'] += " appended"

    config['__jinja_expand'] = True
    assert config['package_manager.conf'] == "initial appended"
    config['__jinja_expand'] = False

    config['package_manager.conf'] = "replaced"

    config['__jinja_expand'] = True
    assert config['dnf.conf'] == config['yum.conf'] == 'replaced'

    config['variable'] = "content"
    config['package_manager.conf'] += " {{ variable }}"

    assert config['dnf.conf'] == config['yum.conf'] == 'replaced content'


@pytest.mark.xfail
def test_that_access_doesnt_affect_value():
    config = TemplatedDictionary()
    config['a'] = {}
    config['a']['b'] = '{{ b }}'
    config['__jinja_expand'] = True

    # access it, and and destroy 'a' (shouldn't happen)
    assert '' == config['a']['b']

    # we set b, but it is not propagated to a.b because a.b was already
    # accessed - and that rewrote a.b to ''.  So even after setting b properly,
    # a.b stays empty.
    config['b'] = 'b'
    assert 'b' == config['a']['b']


def test_not_detected_recursion():
    config = TemplatedDictionary()
    config['a'] = '{{ a }}'
    config['b'] = '{{ a }}'
    config['__jinja_expand'] = True

    # TODO: should this throw exception?  We might hypotetically use this
    # "problem" to assure that some values are unexpanded.
    assert config['a'] == '{{ a }}'
    assert config['b'] == '{{ a }}'


def test_too_deep_recursion():
    config = TemplatedDictionary()
    config['a'] = '{{ b }}'
    config['b'] = '[ {{ a }} ]'
    config['__jinja_expand'] = True
    with pytest.raises(ValueError):
        # infinite recursion
        config['a']

    config = TemplatedDictionary()
    config['a'] = '{{ b }}'
    config['b'] = '{{ c }}'
    config['c'] = '{{ d }}'
    config['d'] = '{{ e }}'
    config['e'] = '{{ f }}'
    config['f'] = 'f'
    config['g'] = 11
    config['__jinja_expand'] = True

    # this is not yet too deep
    assert config['b'] == 'f'

    # but this is too deep
    with pytest.raises(ValueError):
        config['a']


def test_many_newlines():
    # rhbz#1806482
    config = TemplatedDictionary()
    string = "\n\n\n\n\n\na\n\n\n\n\n\n"
    config['a'] = string
    config['__jinja_expand'] = True
    assert config['a'] == string
