---
layout: default
title: How do we release Mock
---

# Mock versions

We keep the "major.minor" versioning scheme, and we bump the "major" number when
some important/notable new feature appears, or when breaking change happens.

For the `mock-core-configs` package, the `major` number reflects the latest
Fedora **branched** version from Rawhide.

Note we maintain multiple Mock versions in parallel.  See `README.md` file
for more info.  You might need to repeat the steps described in this document
multiple times.  Even though `tito` should have appropriate releasers
configured, please be careful when updating various distributions and use the
correct branch version.

## Fedora Rawhide branching

When you plan to release a new mock-core-configs for a new Fedora version being
branched from Rawhide, there's a script in releng/rawhide-branching.sh that
helps you to setup a correct configuration layout.

## Release checklist overview

1. change to the correct local branch, e.g. `main`

        $ git checkout main

2. fetch git remote, and propose local-only patches (if any)

        $ git pull --rebase main

3. Prepare a testing machine

   It's strongly discouraged to run the test-suite locally, because certain
   rather intrusive system configuration is needed (LVM partitions, `/var/lib`
   space requirements, etc.).  Please allocate some disposable VM (with root
   partition of size ">= 60GB"), and run the test-suite there.

   The system can be preconfigured using the Ansible playbook provided in the
   Mock git repository.  Play it like `./integration-tests/setup-box`.

    Then just:

        $ ssh root@<IP_ADDRESS_OF_TESTED_MACHINE>
        # su - mockbuild


4. Install the snapshot version of Mock/configs (to test the right pre-release
   version)

        $ cd mock && cd mock
        $ tito build --rpm -i
        $ cd ../mock-core-configs
        $ tito build --rpm -i
        $ cd ..

5. Run the test-suite

        $ cd mock/behave
        $ behave        # the new test-suite
        $ cd ../mock    # the old test-suite
        $ make check 1>/tmp/test-output.txt  2>&1

   Fix the test-suite errors first, before moving to the next step.

6. Prepare release notes.

        $ git mv docs/Release-Notes-Next.md docs/Release-Notes-4.2.md
        $ vim docs/Release-Notes-4.2.md

   Add list of contributing authors:

       $ git log mock-4.1-1..HEAD --format="%aN" mock/ | sort | uniq
       $ git log mock-core-configs-38.1-1..HEAD --format="%aN" mock-core-configs/ | sort | uniq

7. On your box (you need push-access rights), tag the git tree:

       $ cd ./mock  # or cd ./mock-core-configs
       $ tito tag --use-version 3.0  # major.minor according to policy

   When you release both mock and mock-core-configs together, you
   likely want to (a) first tag 'mock-core-configs' package with bumped
   'Requires: mock >= ??', (b) bump 'Conflicts: mock-core-configs < ??' in
   mock.spec and (c) then tag new mock version.

8. Push the tito-generated commits to the upstream repo

   Suggestion: You can calmly avoid doing direct pushes.  You can simply remove
   the local-only git tag created by tito, and submit PR the normal way:

       $ git tag -d mock-4.1-1  # drop tag
       $ git branch new-version proposal
       $ git push yourremote new-proposal
       ...
       remote: Create a pull request for 'new-proposal' on GitHub by visiting:
       remote:      https://github.com/praiskup/mock/pull/new/new-proposal
       ...

    These tito-generated commits can calmly be squashed, updated, etc. (you may
    include documentation fixes there).  Just don't forget to re-add the dropped
    tag back (if dropped) 'git tag mock-4.1-1'.  Alternatively just `git push`
    the commits.

9. Push the git tags upstream

       $ git push --tags

10. Release for EPEL and Fedora

       $ # make sure that .tito/releasers.conf is up to date
       $ cd ./mock  # or mock-core-configs
       $ tito release fedora-git-all

11. publish tgz

    - The `tito release` calls above uploaded the tarball to Fedora DistGit
      lookaside cache.  You can simply use those.  Alternative you should be able
      to generate the same (byte-by-byte) tarball via `tito build --tgz`

    - Go to the [releases page](https://github.com/rpm-software-management/mock/releases),

    - click "Draft new release"

    - Choose existing tag. E.g., `mock-1.4.9-1 @ main`

    - Enter the same tag as release "title"

    - Attach the tarball binary

12. Once the builds finish (successfully) you should push the just built packages
   to their respective testing repositories. This can be done either with the
   Bodhi WebUI at https://bodhi.fedoraproject.org/ or if there are no other
   package dependencies, using the 'fedpkg update' command (you can specify
   multiple builds, even for multiple fedora/epel versions, like
   `[mock-1.35-1.fc38, mock-1.35-1.fc37, ...]`).  Note that you do not need to
   do this for the Fedora Rawhide build since it automatically gets pushed to
   testing.

13. Announce the release

    We typically send announcement e-mails to
    [bulidsys@lists.fedoraproject.org](https://lists.fedoraproject.org/archives/list/buildsys@lists.fedoraproject.org/),
    and depending on the severity of the release also to
    [devel@lists.fedoraproject.org](https://lists.fedoraproject.org/archives/list/devel@lists.fedoraproject.org/).

    We also announce in [Fosstodon CPT's space](https://fosstodon.org/@fedoracpt).

    Typical e-mail looks like:

        Subject: Mock v4.0 released (and mock-core-configs v38.5)

        Hello maintainers!

        I'm glad I can announce that we have a new release of Mock v
        (the chroot build environment manager for building RPMs).

        <SHORT SUMARY ann LIST OF IMPORTANT CHANGES>

        Full release notes:

            https://rpm-software-management.github.io/mock/Release-Notes-4.0

        The updated packages are in Bodhi:

        [Fedora 38]:
        [Fedora 37]:
        [EPEL 9]:
        [EPEL 8]:

        Happy building!

14. Do the post-release administrivia

    - `cp docs/Release-Notes-Template.md docs/Release-Notes-Next.md`, fill the
      template with known info (you may ask the future PR contributors to
      fill the "NEWS" sections during review!)

    - vim mock/mock.spec, and "bump" the version with post-release tag, e.g.
      from `4.1` to `4.1.post1`.  This assures that any pre-release NVR built
      from upstream git will be higher than the NVR from Fedora (typically,
      Fedora bumps the Release `1 => 2` at some point, but we Version from git
      is still higher).  Also, any subsequent PR that touches
      `mock-core-configs` so that the package requires newer Mock version, you
      may specify `Requires: mock >= 4.1.post1` and eventually bump to `post2`,
      `post3`, etc.

    - `git commit -m 'Post-release administrivia'` (review and push)
