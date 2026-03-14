The new SBOM generator plugin provides comprehensive visibility into the build 
environment by capturing the **complete build toolchain** installed in the 
chroot, including per-package GPG signatures and vendor metadata. It establishes 
full audit traceability by linking built RPMs with their original source 
tarballs and patches, including SHA-256 hashes. Supporting both CycloneDX 1.5 
and SPDX 2.3 formats, the plugin leverages a chroot-native analysis model to 
ensure high metadata accuracy for cross-distribution builds and compatibility 
with modern security scanners.
