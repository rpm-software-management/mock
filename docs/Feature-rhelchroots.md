---
layout: default
title: Feature RHEL chroots
---
## Build package for RHEL

Previously, when you had to build a package for RHEL you had to use `epel-7-x86_64` chroot (or similar). This chroot is made of CentOS plus EPEL. This causes a problem when you want to use real RHEL for some reason. E.g., when new RHEL is out, but CentOS not yet.

To build for RHEL you have to [Red Hat subscription](https://www.redhat.com/en/store/linux-platforms). You can use your existing subscription or you can use [free of charge subscription](https://developers.redhat.com/blog/2016/03/31/no-cost-rhel-developer-subscription-now-available/).

### Mock RHEL configs

Mock provides `rhel-<RELEASEVER>-<TARGET_ARCH>` configs which use pure RHEL.
There are also `rhel+epel-<RELEASEVER>-<TARGET_ARCH>` configs which use RHEL plus EPEL.

### Subscription configuration with Simple Content Access

If you have [Simple Content Access](https://access.redhat.com/articles/simple-content-access#how-do-i-enable-simple-content-access-for-red-hat-subscription-management-2) enabled,
all you need to do is register the machine you are running mock on.
The register command will prompt you for your username and password.

```
$ sudo subscription-manager register
```

After this the RHEL mock configs should work without further action.

```
$ mock -r rhel-9-x86_64 --shell
```

Optionally, you can disable the subscription-manager dnf plugin if you do not need subscription repos directly on your machine.

```sh
$ sudo subscription-manager config --rhsm.auto_enable_yum_plugins 0
$ sudo sed -e '/^enabled=/ s/1/0/' -i /etc/dnf/plugins/subscription-manager.conf
```

### Multiple client keys

If there are multiple client keys,
mock takes the first one in `glob("/etc/pki/entitlement/<numeric-part>-key.pem")` output.
But users still generate configure `config_opts['redhat_subscription_key_id']` in mock configuration,
or on command line `--config-opts=redhat_subscription_key_id=<ID>`.
