---
layout: default
title: Plugin rpkg preprocessor
---

This plugin allows you to run preprocessing on an input spec file just before srpm build is started.

Preprocessing is implemented by a simple `preproc` language which allows you to place: `{% raw %}{{{ bash_code }}}{% endraw %}` tags into any text file. When you run such text file through `preproc` command-line utility, a "rendered" text file is output where all the `{% raw %}{{{ bash_code }}}{% endraw %}` tags are now replaced by standard output of the executed `bash_code` that was inside the `{% raw %}{{{ }}}{% endraw %}` tags.

`preproc` also allows you to load a certain library of macros (by `-s` switch on its command-line) which are essentially just bash functions that you can afterward use from any `{% raw %}{{{&nbsp;}}}{% endraw %}` tag in the input text file.

One such library is called `rpkg-macros` and its macros are documented [here](https://docs.pagure.org/rpkg-util/v3/macro_reference.html). These macros are specialized to render rpm spec file's dynamically based on surrounding git metadata. They need the spec file you are building srpm from to be placed in a git repository.

`preproc` with the `rpkg-macros` library loaded is exactly what is used to perform preprocessing on spec file by the `rpkg_preprocessor` plugin. Instead of calling `preproc` directly with the `-s` switch to load `rpkg-macros`, we use a tiny `preproc-rpmspec` wrapper that does this for us but it could be done either way.

Note that just enabling the plugin is not enough to get spec file preprocessed. You additionally need `rpkg.conf` file placed next to the spec file with the following content:

    [rpkg]
    preprocess_spec = True

That's because for some packages you might want to have preprocessing disabled even though the plugin is globally enabled. Note that even if you have rpkg preprocessing globally enabled (e.g. in `/etc/mock/site-defaults.cfg`) and the `rpkg.conf` file is present with the required content to enable preprocessing, you still have an option to disable preprocessing on command-line by using mock's option `--disable-plugin=rpkg_preprocessor`. There is also `--enable-plugin=rpkg_preprocessor` to do the opposite.

There is currently only one mock command that does invoke the `rpkg_preprocessor` plugin (if all the conditions above are satisfied): `mock --buildsrpm`. This plugin is not employed for rebuilding existing srpms with `mock --rebuild` command or any other mock operation currently.

An example usage with the `mock --buildsrpm` command is:

    $ cd <package_git_repository>
    $ mock --buildsrpm --spec ./my_package.spec.rpkg --sources .

This will run preprocessing on `my_package.spec.rpkg` and the output spec file will be then handed over to `rpmbuild` to build srpm from it.

`.rpkg` extension for rpm spec files containing rpkg macros is optional but recommended.

## Configuration

The plugin supports the following configuration options (mentioned together with the default values):

    config_opts['plugin_conf']['rpkg_preprocessor_enable'] = False
    config_opts['plugin_conf']['rpkg_preprocessor_opts']['requires'] = ['preproc-rpmspec']
    config_opts['plugin_conf']['rpkg_preprocessor_opts']['cmd'] = '/usr/bin/preproc-rpmspec %(source_spec)s --output %(target_spec)s'

* `rpkg_preprocessor_enable` option switches the plugin on and off
* `requires` option specifies requirements to perform the preprocessing operation. The operation is done in a chroot where srpm is built afterwards so the tool(s) to perform preprocessing need to be installed there first
* `cmd` option defines the actual command to run the preprocessing operation.

`requires` and `cmd` options are there for possible future updates in the used tooling. You don't need to modify these options to get the default preprocessing functionality. The only line needed in `/etc/mock/site-defaults.cfg` to enable this plugin is:

    config_opts['plugin_conf']['rpkg_preprocessor_enable'] = True

This plugin is available since mock-x.x.x.
