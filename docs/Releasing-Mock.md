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

For Rawhide releases, you'll primarily be updating mock-core-configs only. Follow the
steps in the release checklist, but focus only on the mock-core-configs parts.
Be sure to use the `--config-only` flag when generating release notes.

## Release checklist overview

0. Make sure all GitHub CI checks are passing for the latest commit

1. Change to the correct local branch, e.g. `main`

        $ git checkout main

2. Fetch git remote, and propose local-only patches (if any)

        $ git pull --rebase main

3. If you want to propose the release through a PR, switch to a new branch

        $ git checkout -b release-2024-05-15

5. Prepare release notes. Use the going-to-be-released version, not
   the current version.

   For a full release (both mock and mock-core-configs):
        
        $ sudo dnf install towncrier
        $ ./releng/generate-release-notes --use-version 5.1
        $ vim docs/Release-Notes-5.1.md  # modify manually!
        
   For a mock-core-configs only release:
   
        $ ./releng/generate-release-notes --use-version 40.3 --config-only
        $ vim docs/Release-Notes-Configs-40.3.md  # modify manually!

   Don't forget to manually modify ./docs/index.md and mention the new release.

   Add list of contributing authors:

   For mock:
       $ git log mock-4.1-1..HEAD --format="%aN" mock/ | sort | uniq
   
   For mock-core-configs:
       $ git log mock-core-configs-38.1-1..HEAD --format="%aN" mock-core-configs/ | sort | uniq

6. Commit all the pending changes

7. On your box (you need push-access rights), tag the git tree:

   For a full release (both mock and mock-core-configs):
       
       # First tag mock-core-configs
       $ cd ./mock-core-configs
       $ tito tag --use-version 40.3  # major.minor according to policy
       
       # Then update mock's spec and tag mock
       # Update 'Conflicts: mock-core-configs < ??' in mock.spec
       $ cd ./mock
       $ tito tag --use-version 5.1  # major.minor according to policy

   For a mock-core-configs only release:
   
       $ cd ./mock-core-configs
       $ tito tag --use-version 40.3  # major.minor according to policy
       
   For a mock only release:
   
       $ cd ./mock
       $ tito tag --use-version 5.1  # major.minor according to policy

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

9. Push the git tags upstream, e.g.

   For mock-core-configs:
       $ git push origin mock-core-configs-40.4-1
       
   For mock:
       $ git push origin mock-5.1-1

10. Release for EPEL and Fedora

    $ # make sure that .tito/releasers.conf is up to date
    
    For mock-core-configs:
    $ cd ./mock-core-configs
    $ tito release fedora-git-all
    
    For mock:
    $ cd ./mock
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

    For a full release (both mock and mock-core-configs):

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
