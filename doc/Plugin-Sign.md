---
layout: default
title: Plugin Sign
---

The Sign plugin can call command (from the host) on the produced rpms.

It was primary created for signing packages, but can call anything you want to.

## Configuration

The Sign plugin is disabled by default. To enable it, add this code to configure file:

    config_opts['plugin_conf']['sign_enable'] = True
    config_opts['plugin_conf']['sign_opts'] = {}
    config_opts['plugin_conf']['sign_opts']['cmd'] = 'rpmsign'
    config_opts['plugin_conf']['sign_opts']['opts'] = '--addsign %(rpms)s'

The variable %(rpms)s will be expanded to package file name. This command will run as unprivileged and will get all your environment variables and especially it will run in your $HOME. So `~/.rpmmacros` will be interpreted.

Since mock-1.2.14 there is also available variable `%(resultdir)`, which will be expanded to name of directory where are final rpm packages.
