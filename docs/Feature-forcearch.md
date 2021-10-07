---
layout: default
title: Feature forcearch
---
## Forcearch

Previously you were able to only build for compatible architectures. I.e., you can build `i386` package on `x86_64` architecture. When you tried to build for incompatible architecture, you get this error:

```
$ mock -r fedora-28-ppc64le shell
ERROR: Cannot build target ppc64le on arch x86_64, because it is not listed in legal_host_arches ('ppc64le',)
```

Now, you can build for any architecture using a new option --force-arch ARCH. [GH#120](https://github.com/rpm-software-management/mock/issues/120) You have to have installed package `qemu-user-static`, which is a new soft dependence. Try this:

```
$ sudo dnf install qemu-user-static
$ mock -r fedora-28-ppc64le --forcearch ppc64le shell
```

and you get the prompt in PPC64LE Fedora. You can do this for any architecture supported by QEMU.
You got just `INFO` in the log stating:

```
INFO: Unable to build arch ppc64le natively on arch x86_64. Setting forcearch to use software emulation.
```


Note: Do not confuse `--forcearch` and `--arch` which are very different options.

:warning: `qemu-user-static` emulates **user** space, but cannot emulate **kernel** space. If your package need some architecture specific kernel calls or e.g., is parsing output of `lscpu` then this feature is not for you. :(

This has been added to Mock 1.4.11.

Since version 2.0 you do not need to use `--forcearch` as Mock will detect that you want to use different than your native architecture and use qemu-user-static automatically.
