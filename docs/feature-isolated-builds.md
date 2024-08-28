---
layout: default
title: Isolated builds with Mock
---

Isolated builds with Mock
=========================

Mock (v5.7+) supports isolated RPM builds, sometimes referred to as "hermetic"
or "offline" builds.  For more details, see the
[SLSA "isolated" definition][SLSA].

Quick start
-----------

For the impatient, the TL;DR steps of the HOWTO are as follows:

    # we want to build this package
    srpm=your-package.src.rpm

    # we'll create a local repository with pre-fetched RPMs/bootstrap
    repo=/tmp/local-repo

    # resolve build deps for the given SRPM, in this case for Fedora Rawhide
    mock --calculate-build-dependencies -r fedora-rawhide-x86_64 "$srpm"

    # find the lockfile in Mock's resultdir
    lockfile=/var/lib/mock/fedora-rawhide-x86_64/result/buildroot_lock.json

    # create a local RPM repository (+ download bootstrap image)
    mock-isolated-repo --lockfile "$lockfile" --output-repo "$repo"

    # perform the isolated build!
    mock --isolated-build "$lockfile" "$repo" "$srpm"

What an "isolated build" is..
-----------------------------

The term "isolated build" is often used in different contexts, even within
Mock's terminology. Historically, when we said that "Mock isolates the build,"
we typically meant that Mock creates a *buildroot* (also referred to as a *build
directory* or *build chroot*) and runs the (Turing-complete, and thus
potentially insecure) *RPM build* process (i.e., a call to `/usr/bin/rpmbuild`)
inside it.  In this sense, Mock "isolates" the RPM build process from the rest
of the system, or protects the system from potential mishaps.  However, the
**buildroot preparation** process was never "isolated" in this manner—only the
*RPM build* was.  Even the *RPM build* "isolation" was always performed on a
best-effort basis.  For more details, see [Mock's Scope](index).

When we now talk about making builds and the corresponding built artifacts
safer, more predictable, and more reproducible, we refer to the [SLSA
isolation][SLSA] definition.  This involves using Mock in an *isolated*
environment, free from unintended external influence.

Mock itself doesn't aim to provide this level of *isolation*.  Mock is still
just a tool that runs in "some" build environment to perform the `SRPM → RPM`
translation.  In such an environment, the Mock process can be tampered with by
other processes (potentially even root-owned), and as a result, the artifacts
may be (un)intentionally altered.  Therefore, the preparation of the environment
to **run Mock** and the **isolation** itself is the responsibility of a
different tool (for example, `podman run --privileged --network=none`).

So, what does Mock `--isolated-build` do if it doesn't isolate?
Essentially, it just does less work than it usually does!  It optimizes out any
action (primarily during the *buildroot* preparation) that would rely on
"external" factors—specifically, it never expects Internet connectivity.
However, for the eventual build to succeed, **something else** still needs to
perform these omitted actions.  Every single component required for *buildroot*
preparation must be prepared in advance for the `mock --isolated-build`
call (within **the** properly *isolated* environment, of course).


Challenges
----------

You’ve probably noticed that what used to be a simple command—like
`mock -r "$chroot" "$srpm"`—has now become a more complicated set of commands.

This complexity arises because the *buildroot* in Mock is always prepared by
installing a set of RPMs (Mock calls DNF, DNF calls RPM, ...), which normally
requires a network connection.

Additionally, it’s not always guaranteed that the DNF/RPM variant on the build
host (e.g., an EPEL 8 host) is sufficient or up-to-date for building the target
distribution (e.g., the newest Fedora Rawhide).  Therefore, we need network
access [to obtain the appropriate bootstrap tooling](Feature-bootstrap).

The [dynamic build dependencies][] further complicate the process.  Without
them, we could at least make the `/bin/rpmbuild` fully offline—but with them,
it’s not so simple. Mock needs to interrupt the ongoing *RPM build* process,
resolve additional `%generate_buildrequires` (installing more packages on
demand), restart the *RPM build*, interrupt it again, and so on. This process
also requires a network connection!

All of this is further complicated by the goal of making the *buildroot* as
*minimal* as possible—the fewer packages installed, the better. We can’t even
afford to install DNF into the buildroot, and as you’ve probably realized, we
definitely don’t want to blindly install all available RPMs.


The solution
------------

To address the challenges, we needed to separate the online
(`--calculate-build-dependencies`) and offline (`--isolated-build`) tasks
that Mock performs.

1. **Online Tasks:** These need to be executed first.  We let Mock prepare the
   *buildroot #1* for the given *SRPM* (using the standard "online" method) and
   record its *lockfile*—a list of all the resources obtained from the network
   during the process.

   The format of lockfile is defined by provided JSON Schema file(s), see
   documentation for the [buildroot_lock plugin](Plugin-BuildrootLock).

   **Note:** The *buildroot* preparation also includes the installation of
   dynamic build dependencies!  Therefore, we **have to start an RPM build**.
   Although we don’t finish the build (we terminate it once the
   `%generate_buildrequires` is resolved, before reaching the `%build` phase,
   etc.), it must be initiated.

2. **Offline Repository Creation:** With the *lockfile* from the previous step,
   we can easily retrieve the referenced components from the network.  The Mock
   project provides an example implementation for this step in the
   `mock-isolated-repo(1)` utility.  This tool downloads all the referenced
   components from the internet and places them into a single local
   directory—let's call it an *offline repository*.

   **Note:** This step doesn’t necessarily have to be done by the Mock project
   itself. The *lockfile* is concise enough for further processing and
   validation (e.g., ensuring the set of RPMs and the buildroot image come from
   trusted sources) and could be parsed by build-system-specific tools like
   [cachi2][] (potentially in the future).

3. **Offline Build:** With the *srpm* and the *offline repository*, we can
   instruct Mock to restart the build using the `--isolated-build
   LOCKFILE OFFLINE_REPO SRPM` command. The *lockfile* is still needed at this
   stage because it contains some of the configuration options used in step 1
   that must be inherited by the current Mock call.

   This step creates a new *buildroot #2* using the pre-downloaded RPMs in the
   *offline repository* (installing them all at once) and then (re)starts the
   RPM build process.

You might notice that some steps are performed twice, specifically downloading
the RPMs (steps 1 and 2) and running the RPM build (steps 1 and 3).  This
duplication is a necessary cost (in terms of more resources and time spent on
the build) to ensure that step 3 is _fully offline_.  In step 3, the *offline*
RPM build is no longer interrupted by an *online* `%generate_buildrequires`
process—dependencies are already installed!

Also, while you can calmly experiment with


    mock --calculate-build-dependencies -r fedora-rawhide-x86_64 "$srpm"
    mock --no-clean -r fedora-rawhide-x86_64 "$srpm"

and it is very close to the TL;DR variant, such an approach is not the same
thing!  The *buildroot #1* **was not** prepared by Mock in **isolated**
environment.

Limitations
-----------

- Let us stress out that this feature itself, while related or at least a bit
  helpful, doesn't provide reproducible builds.  For reproducible builds, build
  systems need to take in account state of host machine, the full
  software/hardware stack.  There's still a big influence of external factors!

- We rely heavily on
  the [Bootstrap Image feature](Feature-container-for-bootstrap).  This allows
  us to easily abstract the bootstrap preparation tasks, which would otherwise
  depend heavily on the system's RPM/DNF stack, etc.

  For now, we also require the Bootstrap Image to be *ready*.  This simplifies
  the implementation, as we don't need to recall the set of commands (or list of
  packages to install into) needed for bootstrap preparation.

- It is known fact that *normal builds* and *isolated builds* may result in
  slightly different outputs (at least in theory).  This issue relates to the
  topic of *reproducible builds*.  Normally, the *buildroot* is installed using
  several DNF commands (RPM transactions), whereas the *isolated* build installs
  all dependencies in a single DNF command (RPM transaction).  While this
  difference might cause the outputs of *normal* and *isolated* builds to vary
  (in theory, because the chroot depends on RPM installation order), it OTOH
  introduces more determinism!

- The *lockfile* provides a list of the required RPMs, referenced by URLs.
  These URLs point to the corresponding RPM repositories (online) from which
  they were installed in step 1.  However, in many cases, RPMs are downloaded
  from `metalink://` or `mirrorlist://` repositories, meaning the URL might be
  selected non-deterministically, and the specific mirrors chosen could be
  rather ephemeral.  For this reason, users should—for isolated builds—avoid
  using mirrored repositories (as in the case of Koji builders) or avoid making
  large delays between step 1 and step 2.

[SLSA]: https://slsa.dev/spec/v1.0/requirements
[dynamic build dependencies]: https://github.com/rpm-software-management/mock/issues/1359
[cachi2]: https://github.com/containerbuildsystem/cachi2
