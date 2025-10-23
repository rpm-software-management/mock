---
layout: default
title: Release Notes - Mock 6.5
---

## [Release 6.5](https://rpm-software-management.github.io/mock/Release-Notes-6.5) - 2025-10-23


### Changes

- The suppress-sync option that was introduced in the previous release caused
  regression in some packages that use `sync()` during `%check`. Because of that,
  it was disabled by default, and you can enable it as opt-in.
  [#1641](https://github.com/rpm-software-management/mock/issues/1641) 


#### The following contributors have contributed to this release:

- Marián Konček
- Miroslav Suchý

Thank You!
