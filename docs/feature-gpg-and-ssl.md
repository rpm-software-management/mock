---
layout: default
title: GPG keys and SSL certificates
---

## GPG Keys

When you want to verify GPG keys during installation in build root you can use something like in the config:

    config_opts['dnf.conf'] = """
    ... SNIP
    [appstream]
    name=CentOS Stream $releasever - AppStream
    metalink=https://mirrors.centos.org/metalink?repo=centos-appstream-$releasever-stream&arch=$basearch
    gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official
    gpgcheck=1
    ... SNIP
    """

The path in `gpgkey` refers to the path in a buildchroot. How do you get your GPG key to buildchroot? There are several ways:

### Distribution-GPG-Keys

The package `distribution-gpg-key` is a requirement of Mock and is installed into buildchroot. The easiest way
is to add your package to [distribution-gpg-key project](https://github.com/xsuchy/distribution-gpg-keys/) and then
your key will be automatically present in both of host and buildroot.

This is the preferred way for any new config added to `mock-core-configs`.

### Local key

Any file named `RPM-GPG-KEY-*` in the `/etc/pki/mock/` on the host is copied to buildchroot to the same path.

You can use it for your personal GPG keys.

## SSL certificates


Mock copy whole `/etc/pki/ca-trust/extracted` directory from the host to chroot. So the
chroot environment should recognize all SSL certificates your host knows.
If you need to add some specific certificate, you can add this part in your config:

    # Copy host's SSL certificate bundle ('/etc/pki/tls/certs/ca-bundle.crt') into
    # specified location inside chroot.  This usually isn't needed because we copy
    # the whole /etc/pki/ca-trust/extracted directory recursively by default, and
    # Fedora or EL systems work with that.  But some destination chroots can have
    # different configuration, and copying the bundle helps.
    #config_opts['ssl_ca_bundle_path'] = None
