---
layout: default
title: Feature RHEL chroots
---
## Build package for RHEL

Previously, when you had to build a package for RHEL you had to use `epel-7-x86_64` chroot (or similar). This chroot is made of CentOS plus EPEL. This causes a problem when you want to use real RHEL for some reason. E.g., when new RHEL is out, but CentOS not yet.

To build for RHEL you have to [Red Hat subscription](https://www.redhat.com/en/store/linux-platforms). You can use your existing subscription or you can use [free of charge subscription](https://developers.redhat.com/blog/2016/03/31/no-cost-rhel-developer-subscription-now-available/).


### Register:

```
$ subscription-manager register (--serverurl subscription.rhsm.stage.redhat.com) \
 --username username \
 --password password
```

Check available pools:

```
$ subscription-manager list --all --available
...
Pool ID:  <THE_POOL_ID>
...
```

Obtain the keypair:

```
# subscription-manager attach --pool <THE_POOL_ID>
...

$ ls /etc/pki/entitlement
<KEY_ID>-key.pem  <KEY_ID>.pem
```

And try mock:

```
$ mock -r rhel-8-x86_64 --shell
...
```

Mock provides `rhel-8-*` and `rhel-7-*` configs which use pure RHEL. And then there are `rhelepel-8-*` config which use RHEL 8 plus EPEL.

If there are multiple client keys, mock takes the first one in
glob("/etc/pki/entitlement/<numeric-part>-key.pem") output.  But users
still generate configure `config_opts['redhat_subscription_key_id']` in mock
configuration, or on command line  `--config-opts=redhat_subscription_key_id=<ID>`.
