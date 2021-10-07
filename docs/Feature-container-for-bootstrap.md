---
layout: default
title: Feature container for bootstrap
---

## Container image for bootstrap

In past, we had some incompatibilities between host and build target. They were, in fact, small. Like using a different package manager. Some were big. Like, the introduction of Weak and Rich dependencies. For this reason, we introduced [bootstrap](Feature-bootstrap). But then comes [zstd payload](https://fedoraproject.org/wiki/Changes/Switch_RPMs_to_zstd_compression). This is a new type of payload. And to install packages with this payload, you need rpm binary, which supports this payload. This is true for all current Fedoras. Unfortunately, neither RHEL 8 nor RHEL 7 supports this payload. So even bootstrap will not help you to build Fedora packages on RHEL 8.

We come up with a nice feature. Mock will not install bootstrap chroot itself. Instead, it will download the container image, extract the image, and use this extracted directory as a bootstrap chroot. And from this bootstrapped chroot install the final one.

Using this feature, **any** incompatible feature in either RPM or DNF can be used in the target chroot. Now or in future. And you will be able to install the final chroot. You do not even need to have RPM on a host. So this should work on any system. Even Debian based. The only requirement for this feature is [Podman](https://podman.io/). Do not forget to install the `podman` package.

This feature is now disabled by default. You can enable it using:

    config_opts['use_bootstrap_image'] = True

It can be enabled or disabled on the command line using `--use-bootstrap-image` or `--no-bootstrap-image` options.

Note however that also this is prerequisite:

    config_opts['use_bootstrap_container'] = True # or --bootstrap-chroot option

To specify which image should be used for bootstrap container you can put in config:

    config_opts['bootstrap_image'] = 'fedora:latest'

This is a general config. Each config has specified its own image specified. E.g. CentOS 7 has `config_opts['bootstrap_image'] = 'centos:7'` in config. So unless you use your own config, you can enable this feature, and the right image will be used.

There is one known issue:

 * Neither Mageia 6 nor 7 works correctly now with this feature.

Technically, you can use any container, as long as there is the required package manager (DNF or YUM). The rest of the needed packages will be installed by mock.
