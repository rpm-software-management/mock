---
layout: default
title: Hermetic builds with Mock
---

Hermetic builds with Mock
=========================

Mock (v5.7+) supports hermetic RPM builds, sometimes referred to as "isolated"
or "offline" builds.  For more details, see the
[SLSA "hermetic" definition][SLSA future].

Quick start
-----------

For the impatient, the TL;DR steps are as follows:

    # we want to build this package
    srpm=your-package.src.rpm

    # we'll create a local repository with pre-fetched RPMs/bootstrap
    repo=/tmp/local-repo

    # resolve build deps for the given SRPM, in this case for Fedora Rawhide
    mock --calculate-build-dependencies -r fedora-rawhide-x86_64 "$srpm"

    # find the lockfile in Mock's resultdir
    lockfile=/var/lib/mock/fedora-rawhide-x86_64/result/buildroot_lock.json

    # create a local RPM repository (+ download bootstrap image)
    mock-hermetic-repo --lockfile "$lockfile" --output-repo "$repo"

    # perform the hermetic build!
    mock --hermetic-build "$lockfile" "$repo" "$srpm"

What an "hermetic build" is..
-----------------------------

The term "isolated build" is often used in different contexts within
Mock's terminology.  Historically, when we said that "Mock isolates the build,"
we typically meant that Mock creates a *buildroot* (also referred to as a *build
directory* or *build chroot*) and runs the (Turing-complete, and thus
potentially insecure) *RPM build* process (i.e., a call to `/usr/bin/rpmbuild`)
inside it.  In this sense, Mock "isolates" the RPM build process from the rest
of the system, or protects the system from potential mishaps.  However, the
**buildroot preparation** process was never "isolated" in this manner—only the
*RPM build* was.  Also, the *RPM build* "isolation" was always performed on a
best-effort basis.  For more details, see [Mock's Scope](index).

This document focuses on making builds and their corresponding artifacts safer,
more predictable, and more reproducible.  When we refer to *isolation*, we are
specifically referencing the [SLSA platform isolation][SLSA].  SLSA outlines
various security levels, and for the future, it introduces the concept of
[*hermetic builds*][SLSA future].  This is where Mock steps in, enabling builds
to be performed in a *hermetic* environment, free from unintended external
influences.

Mock itself doesn't aim to provide this level of *isolation*.  Mock is still
just a tool that runs in "some" build environment to perform the `SRPM → RPM`
translation.  In such an environment, the Mock process can be tampered with by
other processes (potentially even root-owned), and as a result, the artifacts
may be (un)intentionally altered.  Therefore, the preparation of the environment
to **run Mock** and the **isolation** itself is the responsibility of a
different tool (for example, `podman run --privileged --network=none`).

So, what does Mock `--hermetic-build` do if it doesn't isolate?  Essentially, it
just does less work than it usually does!  It optimizes out any action
(primarily during the *buildroot* preparation) that would rely on "external"
factors—specifically, it never expects Internet connectivity.
However, for the eventual build to succeed, **something else** still needs to
perform these omitted actions.  Every single component/artifact required for
*buildroot* preparation must be prepared in advance for the `mock
--hermetic-build` call (within the properly *isolated* or *hermetic*
environment, of course).


Challenges
----------

You've probably noticed that what used to be a simple command—like
`mock -r "$chroot" "$srpm"`—has now become a more complicated set of commands.
This complexity arises because the *buildroot* in Mock is always prepared by
installing a set of RPMs (Mock calls DNF, DNF calls RPM, ...), which normally
requires a network connection.

Additionally, it’s not always guaranteed that the DNF/RPM variant on the build
host is sufficient or up-to-date for building the target distribution (e.g.,
building the newest *Fedora Rawhide* packages on *EPEL 8* host).  Therefore, we
need network access [to obtain the appropriate bootstrap
tooling](Feature-bootstrap).

[Dynamic build dependencies][] add further complexity to the process.  Without
them, we could potentially make the `/bin/rpmbuild` process fully offline—but
with their inclusion, it becomes much more challenging.  Mock must interrupt the
ongoing *RPM build* process, resolve additional `%generate_buildrequires`
(installing more packages on demand), restart the *RPM build*, and potentially
repeat this cycle.  This process also requires an (intermittent) network
connection!

All of this is further complicated by the goal of making the *buildroot* as
*minimal* as possible—the fewer packages installed, the better.  We can’t even
afford to install DNF into the buildroot, and as you've probably realized, we
definitely don’t want to blindly install all available RPMs.


The solution
------------

To address the challenges, we needed to separate the online
(`--calculate-build-dependencies`) and offline (`--hermetic-build`) tasks
that Mock performs.

1. **Online Tasks:** These need to be executed first.  We let Mock prepare the
   *buildroot #1* for the given *SRPM* (using the standard "online" method) and
   record its *lockfile*—a list of all the resources obtained from the network
   during the process.

   The format of lockfile is defined by provided JSON Schema file(s), see
   documentation for the [buildroot_lock plugin](Plugin-BuildrootLock).

   **Note:** The *buildroot* preparation includes the installation of dynamic
   build dependencies!  That's why we have to **initiate** `rpmbuild`.
   But we don’t **finish** the build—we terminate it once the
   `%generate_buildrequires` section is resolved, before reaching the `%build`
   phase.

2. **Offline Repository Creation:** With the *lockfile* from the previous step,
   we can easily retrieve the referenced components from the network.  The Mock
   project provides an example implementation for this step in the
   `mock-hermetic-repo(1)` utility.  This tool downloads all the referenced
   components from the internet and places them into a single local
   directory—let's call it an *offline repository*.

   **Note:** This step doesn't necessarily have to be done by the Mock project
   itself.  The *lockfile* is concise enough for further processing and
   validation (e.g., ensuring the set of RPMs and the buildroot image come from
   trusted sources) and could be parsed by build-system-specific tools like
   [cachi2][] (potentially in the future).

3. **Offline Build:** With the *srpm* and the *offline repository*, we can
   instruct Mock to restart the build using the `--hermetic-build
   LOCKFILE OFFLINE_REPO SRPM` command.  The *lockfile* is still needed at this
   stage because it contains some of the configuration options used in step 1
   that must be inherited by the current Mock call.

   This step creates a new *buildroot #2* using the pre-downloaded RPMs in the
   *offline repository* (installing them all at once) and then (re)starts the
   RPM build process.  This `rpmbuild` run **finishes** though, and provides the
   binary RPM artifacts as usually.

You might notice that some steps are performed twice, specifically downloading
the RPMs (steps 1 and 2) and running the RPM build (steps 1 and 3).  This
duplication is a necessary cost (in terms of more resources and time spent on
the build) to ensure that step 3 is _fully offline_.  In step 3, the *offline*
RPM build is no longer interrupted by an *online* `%generate_buildrequires`
process—dependencies are already installed!

Also, while you can calmly experiment with


    mock --calculate-build-dependencies -r fedora-rawhide-x86_64 "$srpm"
    mock --no-clean -r fedora-rawhide-x86_64 "$srpm"

This approach might seem similar to the TL;DR version, but it's not the same!
There is no *buildroot #1* and *buildroot #2*, only one buildroot.  And that one
was prepared while Mock was online, meaning that something could **have
influenced** the environment preparation, and the subsequent **build**.

Limitations
-----------

- Let us stress out that this feature itself, while related or at least a bit
  helpful for, doesn't provide reproducible builds.  For reproducible builds,
  build systems need to take in account state of host machine, the full
  software/hardware stack.  There's still a big influence of external factors!

- We rely heavily on
  the [Bootstrap Image feature](Feature-container-for-bootstrap).  This allows
  us to easily abstract the bootstrap preparation tasks, which would otherwise
  depend heavily on the system's RPM/DNF stack, etc.

  For now, we also require the Bootstrap Image to be *ready*.  This simplifies
  the implementation, as we don't need to recall the set of commands (or list of
  packages to install into) needed for bootstrap preparation.

- It is known fact that *normal builds* and *hermetic builds* may result in
  slightly different outputs (at least in theory).  This issue relates to the
  topic of *reproducible builds*.  Normally, the *buildroot* is installed using
  several DNF commands (RPM transactions), whereas the *hermetic build* installs
  all dependencies in a single DNF command (single RPM transaction).  While this
  difference might cause the outputs of *normal* and *hermetic* builds to vary
  (in theory, because the chroot shape depends on the complex RPM installation
  order), the *hermetic* variant introduces more determinism!

- The *lockfile* provides a list of the required RPMs, referenced by URLs.
  These URLs point to the corresponding RPM repositories (online) from which
  they were installed in step 1.  However, in many cases, RPMs are downloaded
  from `metalink://` or `mirrorlist://` repositories, meaning the URL might be
  selected non-deterministically, and the specific mirrors chosen could be
  rather ephemeral.  For this reason, users should—for *hermetic* builds, for
  now—avoid using mirrored repositories (and prefer Koji buildroots only) and
  avoid making large delays between step 1 and step 2.  Especially that, at the
  time of writing this document, we know about [two][bug1] [bugs][bug2] that
  will complicate the *lockfile* generation.

[SLSA]: https://slsa.dev/spec/v1.0/requirements
[SLSA future]: https://slsa.dev/spec/v1.0/future-directions
[dynamic build dependencies]: https://github.com/rpm-software-management/mock/issues/1359
[cachi2]: https://github.com/containerbuildsystem/cachi2
[bug1]: https://github.com/rpm-software-management/dnf/issues/2130
[bug2]: https://github.com/rpm-software-management/dnf5/issues/1673
