---
layout: default
title: Release Notes 1.4.13
---

Released on 2018-08-13.

## Features:

- Starting with mock-core-configs version 29.1 the gpg keys for rawhide are checked now.

- There is a new config option `print_main_output`, which allows you to override default behavior:

```
    # By default, mock only prints the build log to stderr if it is a tty; you can
    # force it on here (for CI builds where there is no tty, for example) by
    # setting this to True, or force it off by setting it to False.
    # config_opts['print_main_output'] = None
```

- Following new environment variables are passed to mock from user environment: `http_proxy`, `ftp_proxy`, `https_proxy`, `no_proxy`.

- bash completion has been reworked and is now much simple and hopefully better

- There are new configs for Fedora 30.

## Bugfixes:

- Mockchain will again stop after the first failure if -c or --recurse is not used.

- Commands started by mock will be using `C.UTF-8` locale instead of `en_US.UTF-8`, which does not need to be available.

- There is new default for `nspawn_args`: `config_opts['nspawn_args'] = ['--capability=cap_ipc_lock']`. This will enable cap_ipc_lock in nspawn container, which will allow to use `mlock()` [RHBZ#1580435](https://bugzilla.redhat.com/show_bug.cgi?id=1580435).

- Do not get spec from the command line when using scm [GH#203](https://github.com/rpm-software-management/mock/issues/203)

- use host's resolv.conf when --enable-network is set on cml [RHBZ#1593212](https://bugzilla.redhat.com/show_bug.cgi?id=1593212)

Following contributors contributed to this release:

* Bruno Vernay
* Chuck Wilson
* Jaroslav Škarvada
* Neal Gompa
* Owen W. Taylor
* Seth Wright
* Todd Zullinger
* Tomasz Torcz

Thank you.

Note: version 1.4.12 has been skipped due error discovered during releasing.
