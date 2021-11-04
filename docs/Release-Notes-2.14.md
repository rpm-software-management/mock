---
layout: default
title: Release Notes 2.14
---

Released on - 2021-11-04


## Mock 2.14 has just one regression fix:

* The `--enablerepo` and `--disablerepo` options got broken in v2.13 by the
  `optparse => argparse` rewrite.  This should be fixed now, and the options
  should be working fine.

Thanks to Aleksei Bavshin for reporting the issue in Fedora Bodhi.
