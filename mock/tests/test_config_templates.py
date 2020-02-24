from mockbuild.util import TemplatedDictionary


def test_transitive_expand():
    config = TemplatedDictionary()
    config['a'] = 'test'
    config['b'] = '{{ a }} {{ a }}'
    config['c'] = '{{ b + " " + b }}'
    assert config['c'] == '{{ b + " " + b }}'
    config['__jinja_expand'] = True
    assert config['c'] == 'test test test test'
