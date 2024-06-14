---
layout: default
title: Maintaining ChangeLog
---

# TL;DR - quick start

You typically want to create a markdown snippet with:

    $ towncrier create failed-selinux-mountpoint.bugfix
    Created news fragment at ./releng/release-notes-next/failed-selinux-mountpoint.bugfix
    $ vim ./releng/release-notes-next/failed-selinux-mountpoint.bugfix
    ... document ...
    $ git add ./releng/release-notes-next/failed-selinux-mountpoint.bugfix

Please refer to issues, PRs, bugs, commits using the
`[reference#ID][]` or `[some text][reference#ID]` syntax described below.

# Maintaining ChangeLog

Mock uses the [towncrier](https://github.com/twisted/towncrier) project for
maintaining release notes (aka changelog).  For adding a new Release Notes
entry, provide a markdown file in the
[releng/release-notes-next](https://github.com/rpm-software-management/mock/tree/main/releng/release-notes-next)
drop-in directory.

Each drop-in file is markdown, and the filename must have
`<some-unique-text>.<change_category>` pattern.  The "unique filename" is
important, but the name is not used anywhere (choose wisely to not collide with
other changes in the next release).  For example, let's have a file

    releng/release-notes-next/ssl-certs-fixed.bugfix

with contents like:

    The SSL certificate copying has been fixed [once more][PR#1113] to use our
    own `update_tree()` logic because the `distutils.copy_tree()` was removed
    from the Python stdlib, and the new stdlib alternative `shutil.copytree()`
    is not powerful enough for the Mock use-cases ([issue#1107][]).

## Change categories

Documentation for categories configured in
[towncrier.toml](https://github.com/rpm-software-management/mock/blob/main/towncrier.toml).


1. `breaking`: Incompatible change done.  This is mentioned at the beginning of
   the changelog file to get extra attention.

1. `bugfix`: Some important bug has been fixed in Mock.

1. `feature`: New feature in Mock has been implemented.

1. `config`: Change related to the `mock-core-configs` package.


## Referencing issues or pull-requests

The snippets/drop-in files are in markdown format, so you may simply reference
issues with `[<type>#<id>][]` or `[custom placeholder][<type>#<id>]`.  For
example `[rhbz#123456][]` or `[dumping packages][PR#1210]`.  Currently
implemented types:

1. `rhbz#ID`: generates `https://bugzilla.redhat.com/ID
1. `issue#ID`: generates: `https://github.com/rpm-software-management/mock/issues/ID`
1. `PR#ID`: generates: `https://github.com/rpm-software-management/mock/pull/ID`
1. `commit#HASH`: generates: `https://github.com/rpm-software-management/mock/commit/HASH`
