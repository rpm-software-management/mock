---
layout: default
title: Plugin SCM
---

This plugin provides integration to Scm systems (Git, Svn...).

This module does not use the plugin infrastructure of Mock, it is provided as a standalone package instead, mock-scm, so we dare to call it plugin.

## Configuration

In your config file insert the following lines:


    config_opts['scm'] = True
    config_opts['scm_opts']['method'] = 'git'
    config_opts['scm_opts']['cvs_get'] = 'cvs -d /srv/cvs co SCM_BRN SCM_PKG'
    config_opts['scm_opts']['git_get'] = 'git clone --depth 1 SCM_BRN git://localhost/SCM_PKG.git SCM_PKG'
    config_opts['scm_opts']['svn_get'] = 'svn co file:///srv/svn/SCM_PKG/SCM_BRN SCM_PKG'
    config_opts['scm_opts']['distgit_get'] = 'rpkg clone -a --branch SCM_BRN SCM_PKG SCM_PKG'
    config_opts['scm_opts']['distgit_src_get'] = 'rpkg sources'
    config_opts['scm_opts']['spec'] = 'SCM_PKG.spec'
    config_opts['scm_opts']['ext_src_dir'] = '/dev/null'
    config_opts['scm_opts']['write_tar'] = True
    config_opts['scm_opts']['git_timestamps'] = True
    config_opts['scm_opts']['exclude_vcs'] = True
    config_opts['scm_opts']['package'] = 'mypkg'
    config_opts['scm_opts']['branch'] = 'master'

While you can specify this in configuration file, this is less flexible and you may rather use command line options. E.g. `config_opts['scm_opts']['method'] = 'git'` is the same as `--scm-option method=git` or `config_opts['scm_opts']['branch'] = 'master'` is the same as `--scm-option branch=master`.

## Tar file

When either `write_tar` is set to True or /var/lib/mock/<chroot>/root/builddir/build/SOURCES/ contains `.write_tar`. Mock will create tar file from whole SVN repo. This is what you probably want to. Otherwise you have to manually create the tar file and put it there yourself before you run mock command.

Extension and compression method is chosen automatically according your Source line in spec file. Therefore if there is:

    Source: http://foo.com/%{name}-%{version}.tar.xz

then mock will create tar file with .tar.xz extension and compressed by xz. Similarly if you choose .tar.gz or .tar.bz2 or any other known extension.

### git_timestamps

When `git_timestamps` is set to True, then modification time of each file in GIT is altered to datetime of last commit relevant to each file.
This option is available only to Git method and not for others.

### exclude-vcs

When `exclude-vcs` is set to True, then `--exclude-vcs` option is passed to tar command.

### ext_src_dir

When your source (or patch) file does not exist in `/var/lib/mock/<chroot>/root/builddir/build/SOURCES/` directory then it is looked up in `ext_src_dir` and copy there.

### dist-git

Since version 1.3.4, there is support for [dist-git](https://github.com/release-engineering/dist-git). In fact it can support any DistSVN or DistCVS method. You just specify which command clone the repository (`distgit_get`) and which command retrieve sources (`distgit_src_get`). Mock-scm will then construct SRPM from those spec file and sources. Do not forget to specify `config_opts['scm_opts']['method'] = 'distgit'`

## Example

In this example, mock will clone `master` branch of `github.com/xsuchy/rpmconf.git` and use `./rpmconf.spec` in that directory to build rpm package:

    mock -r fedora-22-x86_64 \
         --scm-enable \
         --scm-option method=git \
         --scm-option package=rpmconf \
         --scm-option spec=rpmconf.spec \
         --scm-option branch=master \
         --scm-option write_tar=True \
         --scm-option git_get='git clone https://github.com/xsuchy/rpmconf.git'

Or you can:

    cp /etc/mock/fedora-22-x86_64.cfg ./my-config.cfg
    vi ./my-config.cfg

put there those lines:

    config_opts['scm'] = True
    config_opts['scm_opts']['method'] = 'git'
    config_opts['scm_opts']['git_get'] = 'git clone https://github.com/xsuchy/rpmconf.git'
    config_opts['scm_opts']['spec'] = 'rpmconf.spec'
    config_opts['scm_opts']['write_tar'] = True
    config_opts['scm_opts']['package'] = 'rpmconf'
    config_opts['scm_opts']['branch'] = 'master'

and then just call

    mock -r ./my-config.cfg
