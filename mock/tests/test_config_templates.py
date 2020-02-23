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
