---
layout: default
title: Release Notes 1.4.14
---

Released on 2019-02-19.

Release together with `mock-core-configs-30.1` which has these changes:

- Added repositories for Fedora 30 (and Fedora 31 repos now points to rawhide).

- distribution-gpg-keys for rhel8beta is being installed directly from Koji, because EPEL8 does not exist yet.

- Fedora 27 config has been moved to `eol` directory.

- `gpgcheck` is enabled for testing and debuginfo now.

- Fedoras 29+ have included modular repos now. Additionally, there is now `module_platform_id` defined in these configs, which allows you to install modules without errors.

## Mock new features:

- All mock configs are parsed and evaluated by [Jinja2](http://jinja.pocoo.org/). Here is small example how it can be used:

```
# define your own config variable
config_opts['fedora_number'] = '30'
config_opts['root'] = 'fedora-{{ fedora_number }}-x86_64'
config_opts['dist'] = 'fc{{ fedora_number }}'
```

Another - more general - example from `site-defaults.cfg`:

```
# You can use jinja templates, e.g.:
# config_opts['foobar'] = '{{ foo }} bar'
# which will result in 'bar bar' (using value defined few lines above)
# more complicated example:
# config_opts['foo'] = "{{ plugin_conf['package_state_enable'] }}"
# which will result in "True"
```

This feature can simplify mock's configs in the future. I intentionally did not use it now, because it is too fresh. Please experiment with this feature on your own and report any error or issues. If there would be none, then I will start using it in main configs.

- Use 32-bit personality for armv7*/armv8* builds.

- You can now specify decompress program for root_cache. This is new default in `site-defaults.cfg` [GH#230](https://github.com/rpm-software-management/mock/issues/230):

```
## decompress_program is needed only for bsdtar, otherwise `compress_program` with `-d` is used
## for bsdtar use "unpigz" or "gunzip"
# config_opts['plugin_conf']['root_cache_opts']['decompress_program'] = "pigz"
```


## Bugfixes:

- Added Scientific Linux on the list of RHEL clones [GH#228](https://github.com/rpm-software-management/mock/issues/228)

- Fixed exclude pattern for BSDTar [GH#219](https://github.com/rpm-software-management/mock/issues/219)

- There used to be living part of `site-defaults.cfg`:

```
config_opts['bootstrap_chroot_additional_packages'] = []
config_opts['bootstrap_module_enable'] = []
config_opts['bootstrap_module_install'] = []
```

This is now commented out by default, and the defaults are set in mock code. You can still override it in `site-defaults.cfg`.

Following contributors contributed to this release:

* Bernhard Rosenkränzer
* František Zatloukal
* Pavel Raiskup
* Petr Junák
* Sam Fowler

Thank you.
