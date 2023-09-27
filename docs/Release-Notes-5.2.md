---
layout: default
title: Release Notes - Mock 5.2
---

Released on 2023-09-27.

### Mock 5.2 new features

- Mock newly logs out its command-line arguments to better deduct what was
  happening at build time.


### Bugfixes

- The fixes introduced in Mock 5.1 included a compatibility issue with Python in
  Enterprise Linux 8 due to a dependency on the `capture_output=True` feature in
  the `subprocess` module, which was added in Python 3.7.  However, EL 8 is
  running on Python 3.6.  This compatibility issue has been resolved in Mock by
  using `stdout=subprocess.PIPE` instead.  This update was made based on a [report
  from Bodhi update](https://bodhi.fedoraproject.org/updates/FEDORA-EPEL-2023-45ace77fca). 
- Previous versions of Mock mistakenly expanded every `~` occurrence
  (tilde character) in the specified source path with `--copyout`.  So
  files `~/foo~bar.txt` were searched on path `/builddir/foo/builddirbar.txt`
  instead of just `/builddir/foo~bar.txt`.  Fixes [rhbz#2239035][]. 
- The Mock state monitoring (creating state.log) was fixed so that Mock, unless
  some exception is raised, always checks that we finished all the states we
  started.

[rhbz#2239035]: https://bugzilla.redhat.com/2239035
