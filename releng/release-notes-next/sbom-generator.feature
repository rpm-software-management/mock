The new SBOM generator plugin provides visibility into the build environment by
capturing the build toolchain packages installed in the chroot (best-effort),
including per-package GPG signature metadata when available. It links built RPMs
with their source tarballs and patches, including SHA-256 hashes where digests
can be collected. Supporting both CycloneDX 1.6 and SPDX 2.3 formats, the plugin
uses host-visible chroot analysis for cross-distribution builds. Collection is
evidence-backed (complete / partial / minimal) and may report gaps when
prebuild or postbuild collectors fail, while remaining compatible with security
scanners, File Integrity Monitoring (FIM), and supply-chain forensic analysis.
