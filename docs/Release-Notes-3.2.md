---
layout: default
title: Release Notes - Mock v3.2
---

Released on 2022-10-14.

## Mock v3.2 changes:

- The `cleanup_on_success=False` needs to use `rpmbuild --noclean` to avoid
  an automatic cleanup of `%{buildroot}` by RPM (we started using `--noclean` in
  [v3.1](Release-Notes-3.1).  The `--noclean` option is though not available on
  old systems (EL6 and older).  The new Mock *v3.2* fixes this, and stops using
  `--noclean` for old target builds.  Related [rhbz#2105393][].

- Files installed into `/var/lib/mock` and `/var/cache/mock` no longer get the
  SGID bit (which enforces `mock` group ownership).  The bit shouldn't be needed
  (by common sense, but also given our testsuite is green), so we dropped the
  bit.  Should you newly have any inconvenience, please report.

- The `simple_load_config()` library method (used e.g. by Fedora Review) was
  simplified so it doesn't attempt to elevate the `mock` group process
  ownership.  Processing Mock's configuration is equal to evaluating a Python
  code, so for security reasons we artificially fail the `simple_load_config()`
  call if executed by root, [rhbz#2080735][].

- Error() (Exception) code was rewritten a bit, so the raised exceptions are
  easily (de-)serializable by the Python pickle library.  We can then e.g.
  naturally handle the exceptions raised by Mock's `fork()` sub-processes
  (exceptions from child processes are pickle-deserialized).  This change could
  potentially affect the `mockbuild:get_class_by_code()` users, if any.

- Mock now better detects the Docker environment run on top of
  Control Group V2, [PR#986][].

- The `--use-bootstrap-image` now works even if `podman` produces an unexpected
  `stderr` output, [PR#954][].

- The `mock-scm` package newly runtime-depends on the `rpkg-util` package.  This
  package is used for building source RPMs from DistGit, fixes [rhbz#2128212][].

- Mock starts using the SPDX format of License field in the spec file.


**Following contributors contributed to this release:**

 * Achal Velani
 * Michael Ho
 * Miroslav Suchý

Thank you.


[rhbz#2105393]: https://bugzilla.redhat.com/2105393
[PR#954]: https://github.com/rpm-software-management/mock/pull/954
[rhbz#2128212]: https://bugzilla.redhat.com/2128212
[rhbz#2080735]: https://bugzilla.redhat.com/2080735
[PR#986]: https://github.com/rpm-software-management/mock/pull/986
