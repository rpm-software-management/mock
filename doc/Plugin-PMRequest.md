---
layout: default
title: Plugin PM Request
---

This plugin listens to requests for package management commands from within the buildroot, using unix socket. It can be used by buildsystems, that have support for communicating with this plugin, to automatically install missing packages if they're available. It's not advised to enable it globally as it affects build reproducibility, instead, it's better to enable it per-build using `--enable-plugin pm_request`. If the plugin was used during the build, it emits a warning at the end that summarizes the commands that were executed.

Currently, automatic installation of build dependencies using this plugin is supported by Java packaging tooling when building with Maven, Gradle or Ivy.

## Configuration

To enable it globally, set the following:

    config_opts['plugin_conf']['pm_request_enable'] = True

To enable it for a single build, use:

    mock --rebuild foo-1.0-1.src.rpm --enable-plugin pm_request

## The protocol

The plugin creates a Unix socket in /var/run/mock/pm-request inside of the chroot and will read the commands from the socket. It also exports environment variable PM_REQUEST_SOCKET with value of the socket path.
For single request, it reads a single line from the socket (don't forget the newline, otherwise it will wait for more input) that is parsed using shell-like quoting (via shlex) and passed to current package manager. After the command completes, it responds with a line containing either "ok" or "nok" denoting whether the command was successful. The output of the package management command is then written to the socket and the connection is closed. Example of a request:

    install foo

Available since mock-1.2.9
