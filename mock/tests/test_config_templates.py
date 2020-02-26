import pytest
from mockbuild.util import TemplatedDictionary


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
