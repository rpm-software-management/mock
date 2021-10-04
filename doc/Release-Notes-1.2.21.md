---
layout: default
title: Release Notes 1.2.21
---

Mock version 1.2.21 is security release. It fixes:

* CVE-2016-6299 - privilige escalation via mock-scm [RHBZ#1375493](https://bugzilla.redhat.com/show_bug.cgi?id=1375493)

Additionally it has those changes:
- root_cache: Mention _root_ cache being created in state updates (log messages)
- Rename mageia pubkey to RPM-GPG-KEY-Mageia
- require generic system-release rather than fedora-release [RHBZ#1367746](https://bugzilla.redhat.com/show_bug.cgi?id=1367746)
