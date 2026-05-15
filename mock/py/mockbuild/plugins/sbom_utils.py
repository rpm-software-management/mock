# -*- coding: utf-8 -*-
# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# License: GPL2 or later see COPYING
# Written by Scott R. Shinn <scott@atomicorp.com>
# Copyright (C) 2026, Atomicorp, Inc.

import os
import re
import subprocess
import hashlib
import traceback
import rpm
from datetime import datetime, timezone

"""
Utility functions for the SBOM generator plugin.
"""


class RpmQueryHelper:
    # pylint: disable=broad-exception-caught
    """Helper class for querying RPM metadata."""

    def __init__(self, buildroot):
        """Initializes the helper with a buildroot for doChroot access."""
        self.buildroot = buildroot

    def _from_chroot_path(self, path):
        """Standardizes from_chroot_path as a fallback for older mock versions."""
        if hasattr(self.buildroot, 'from_chroot_path'):
            return self.buildroot.from_chroot_path(path)

        # Fallback implementation
        rootdir = getattr(self.buildroot, 'rootdir', None)
        if not rootdir:
            return path
        if path.startswith(rootdir):
            rel_path = path[len(rootdir):]
            if not rel_path.startswith("/"):
                rel_path = "/" + rel_path
            return rel_path
        return path

    def _resolve_chroot_path(self, rpm_path):
        """Resolves a host RPM path to its equivalent path inside the chroot if possible."""
        # Check if it's already a chroot path (from_chroot_path returns a path for any file in rootdir)
        chroot_path = self._from_chroot_path(rpm_path)
        if not chroot_path:
            return None

        # Check if it's in the resultdir. If so, it should be in /builddir/build/RPMS
        if rpm_path.startswith(self.buildroot.resultdir):
            filename = os.path.basename(rpm_path)
            # Search in common build directory structures inside the chroot
            search_paths = [
                "/builddir/build/RPMS",
                "/builddir/build/RPMS/x86_64",
                "/builddir/build/RPMS/noarch",
                "/builddir/build/SRPMS",
                "/builddir/build/SOURCES"
            ]
            for search_path in search_paths:
                candidate = os.path.join(search_path, filename)
                # Verify existence via doChroot
                cmd = ["ls", candidate]
                try:
                    res, _ = self.buildroot.doChroot(cmd, shell=False, returnOutput=True, printOutput=False)
                    if res and candidate in res:
                        return candidate
                except Exception:
                    pass
            return None

        return chroot_path

    def generate_purl(self, package_name, version, distro_obj=None, arch=None):
        """Generates a Package URL (PURL) for an RPM package."""
        # pkg:rpm/fedora/curl@7.50.3-1.fc25?arch=i386&distro=fedora-25
        # We simplify to pkg:rpm/distro/name@version?arch=arch
        clean_name = re.sub(r'[^a-zA-Z0-9.-]', '-', package_name)
        purl = f"pkg:rpm/{distro_obj}/{clean_name}@{version}"
        if arch:
            purl += f"?arch={arch}"
        return purl

    def generate_cpe(self, package_name, package_version, vendor=None):
        """Generates a CPE identifier for a package."""
        # CPE format: cpe:2.3:a:{vendor}:{product}:{version}:*:*:*:*:*:*:*:*

        # Default vendor if not provided
        if not vendor or vendor == "(none)":
            vendor = "unknown"

        # Clean up vendor name for CPE
        vendor = re.sub(r'[^a-zA-Z0-9._-]', '_', vendor.lower())

        # Clean up package name for CPE
        product = re.sub(r'[^a-zA-Z0-9._-]', '_', package_name.lower())

        # Clean up version for CPE (remove release part if present)
        version = package_version
        if '-' in version:
            version = version.split('-')[0]  # Remove release part

        # Generate CPE
        cpe = f"cpe:2.3:a:{vendor}:{product}:{version}:*:*:*:*:*:*:*:*"
        return cpe


    def _parse_signature_data(self, sig_data, signature_info):
        """Parses the raw signature string and updates the signature_info dict."""
        if sig_data and sig_data != "(none)" and sig_data != "":
            signature_info["signature_type"] = "GPG"
            signature_info["signature_valid"] = True

            # Parse signature line like:
            # "RSA/SHA256, Fri 08 Nov 2024 ... Key ID ..."
            if "RSA/SHA256" in sig_data:
                signature_info["signature_algorithm"] = "RSA/SHA256"
            elif "DSA/SHA1" in sig_data:
                signature_info["signature_algorithm"] = "DSA/SHA1"
            elif "ECDSA/SHA256" in sig_data:
                signature_info["signature_algorithm"] = "ECDSA/SHA256"
            elif "Ed25519/SHA256" in sig_data:
                signature_info["signature_algorithm"] = "Ed25519/SHA256"

            # Extract key ID
            if "Key ID" in sig_data:
                key_id_match = re.search(r'Key ID ([0-9a-fA-F]+)', sig_data)
                if key_id_match:
                    signature_info["signature_key"] = key_id_match.group(1)

            # Extract date - handle various time formats including EST/EDT
            date_match = re.search(
                r'([A-Za-z]{3} [A-Za-z]{3}\s+\d{1,2} \d{2}:\d{2}:\d{2} \d{4})',
                sig_data
            )
            if date_match:
                signature_info["signature_date"] = date_match.group(1)
        else:
            signature_info["signature_type"] = "unsigned"
            signature_info["signature_valid"] = False

    def get_rpm_metadata(self, rpm_path):
        """Extracts metadata from an RPM file.
        Uses doChroot if the file is within the chroot to ensure compatibility."""
        if not os.path.isfile(rpm_path):
            self.buildroot.root_log.debug(f"RPM file not found: {rpm_path}")
            return {}

        # Try to resolve to a chroot path to prioritize chroot-native analysis
        chroot_path = self._resolve_chroot_path(rpm_path)
        if chroot_path:
            self.buildroot.root_log.debug(f"[SBOM] Using chroot-native rpm for: {chroot_path}")
            return self._get_rpm_metadata_chroot(chroot_path)

        # Fallback to host-native bindings
        self.buildroot.root_log.debug(f"[SBOM] Using host-native analysis for: {rpm_path}")
        return self._get_rpm_metadata_native(rpm_path)

    def _get_rpm_metadata_chroot(self, chroot_rpm_path):
        """Extracts metadata using rpm -qp inside the chroot."""
        fields = {
            "name": "%{NAME}", "version": "%{VERSION}", "release": "%{RELEASE}",
            "arch": "%{ARCH}", "epoch": "%{EPOCH}", "summary": "%{SUMMARY}",
            "license": "%{LICENSE}", "vendor": "%{VENDOR}", "url": "%{URL}",
            "packager": "%{PACKAGER}", "buildtime": "%{BUILDTIME}",
            "buildhost": "%{BUILDHOST}", "sourcerpm": "%{SOURCERPM}",
            "group": "%{GROUP}", "distribution": "%{DISTRIBUTION}",
            "sha256": "%{SHA256HEADER}"
        }

        metadata = {}
        try:
            query = "|".join(fields.values())
            cmd = ["rpm", "-qp", "--queryformat", query, chroot_rpm_path]
            output, _ = self.buildroot.doChroot(
                cmd, shell=False, returnOutput=True, printOutput=False
            )

            if output:
                parts = output.split("|")
                for i, field_name in enumerate(fields.keys()):
                    if i < len(parts):
                        val = parts[i].strip()
                        if field_name == "epoch" and (not val or val == "(none)"):
                            val = "0"
                        metadata[field_name] = val
            return metadata
        except Exception as e:
            self.buildroot.root_log.debug(f"Failed to extract metadata via doChroot for {chroot_rpm_path}: {e}")
            return {}

    def _get_rpm_metadata_native(self, rpm_path):
        """Extracts metadata using native host bindings (fallback)."""
        # pylint: disable=no-member
        try:
            ts = rpm.TransactionSet()
            with open(rpm_path, "rb") as f:
                hdr = ts.hdrFromFdno(f.fileno())

            tag_map = {
                "name": rpm.RPMTAG_NAME, "version": rpm.RPMTAG_VERSION,
                "release": rpm.RPMTAG_RELEASE, "arch": rpm.RPMTAG_ARCH,
                "epoch": rpm.RPMTAG_EPOCH, "summary": rpm.RPMTAG_SUMMARY,
                "license": rpm.RPMTAG_LICENSE, "vendor": rpm.RPMTAG_VENDOR,
                "url": rpm.RPMTAG_URL, "packager": rpm.RPMTAG_PACKAGER,
                "buildtime": rpm.RPMTAG_BUILDTIME, "buildhost": rpm.RPMTAG_BUILDHOST,
                "sourcerpm": rpm.RPMTAG_SOURCERPM, "group": rpm.RPMTAG_GROUP,
                "distribution": rpm.RPMTAG_DISTRIBUTION, "sha256": rpm.RPMTAG_SHA256HEADER
            }

            metadata = {}
            for field_name, tag in tag_map.items():
                value = hdr[tag]
                if field_name == "epoch" and value is None:
                    value = "0"
                elif value is None:
                    value = ""
                elif isinstance(value, bytes):
                    value = value.decode('utf-8', errors='replace')
                metadata[field_name] = str(value)
            return metadata
        except Exception:
            self.buildroot.root_log.debug(f"Failed to extract metadata via native bindings for {rpm_path}")
            return {}



    def get_rpm_file_info(self, rpm_path):
        """Extracts file hashes, ownership, and permissions from an RPM file."""
        chroot_path = self._resolve_chroot_path(rpm_path)
        if chroot_path:
            self.buildroot.root_log.debug(f"[SBOM] Using chroot-native file info for: {chroot_path}")
            return self._get_rpm_file_info_chroot(chroot_path)

        self.buildroot.root_log.debug(f"[SBOM] Using host-native file info for: {rpm_path}")
        return self._get_rpm_file_info_native(rpm_path)

    def _get_rpm_file_info_chroot(self, chroot_rpm_path):
        """Extracts file info using rpm -qp inside the chroot."""
        file_info = {}
        try:
            # Query format for files: path|hash|mode|user|group
            qf = "[%{FILENAMES}|%{FILEDIGESTS}|%{FILEMODES:octal}|%{FILEUSERNAME}|%{FILEGROUPNAME}\\n]"
            cmd = ["rpm", "-qp", "--queryformat", qf, chroot_rpm_path]
            output, _ = self.buildroot.doChroot(
                cmd, shell=False, returnOutput=True, printOutput=False
            )

            # Detect digest algorithm from header
            cmd_algo = ["rpm", "-qp", "--queryformat", "%{FILEDIGESTALGO}", chroot_rpm_path]
            algo_out, _ = self.buildroot.doChroot(
                cmd_algo, shell=False, returnOutput=True, printOutput=False
            )
            try:
                algo = int(algo_out.strip()) if algo_out and algo_out.strip() else 8
            except ValueError:
                algo = 8

            for line in output.splitlines():
                parts = line.split("|")
                if len(parts) >= 5:
                    filename = parts[0]
                    file_info[filename] = {
                        "hash": parts[1] if parts[1] and parts[1] != "(none)" else None,
                        "algo": algo,
                        "permissions": parts[2],
                        "owner": parts[3],
                        "group": parts[4]
                    }
            return file_info
        except Exception as e:
            self.buildroot.root_log.debug(f"Failed to get file info via doChroot for {chroot_rpm_path}: {e}")
            return {}

    def _get_rpm_file_info_native(self, rpm_path):
        """Extracts file information using native host bindings (fallback)."""
        # pylint: disable=no-member
        file_info = {}
        try:
            ts = rpm.TransactionSet()
            # pylint: disable=protected-access
            ts.setVSFlags(rpm._RPMVSF_NOSIGNATURES | rpm._RPMVSF_NODIGESTS)
            with open(rpm_path, "rb") as f:
                hdr = ts.hdrFromFdno(f.fileno())

            basenames = hdr[rpm.RPMTAG_BASENAMES]
            dirnames = hdr[rpm.RPMTAG_DIRNAMES]
            dirindexes = hdr[rpm.RPMTAG_DIRINDEXES]
            filedigests = hdr[rpm.RPMTAG_FILEDIGESTS]
            filemodes = hdr[rpm.RPMTAG_FILEMODES]
            fileusernames = hdr[rpm.RPMTAG_FILEUSERNAME]
            filegroupnames = hdr[rpm.RPMTAG_FILEGROUPNAME]

            try:
                algo = hdr[rpm.RPMTAG_FILEDIGESTALGO]
            except (KeyError, IndexError):
                algo = 8

            file_info = {}
            for i, basename in enumerate(basenames):
                dirname = dirnames[dirindexes[i]]
                if isinstance(dirname, bytes):
                    dirname = dirname.decode('utf-8', 'replace')
                if isinstance(basename, bytes):
                    basename = basename.decode('utf-8', 'replace')
                filename = os.path.join(dirname, basename)

                digest = filedigests[i]
                if isinstance(digest, bytes):
                    digest = digest.decode('utf-8')

                file_info[filename] = {
                    "hash": digest if digest else None,
                    "algo": algo,
                    "permissions": f"0{filemodes[i]:o}",
                    "owner": fileusernames[i].decode('utf-8', 'replace') if isinstance(fileusernames[i], bytes) else fileusernames[i],
                    "group": filegroupnames[i].decode('utf-8', 'replace') if isinstance(filegroupnames[i], bytes) else filegroupnames[i]
                }
            return file_info
        except Exception:
            return {}

    def get_rpm_dependencies(self, rpm_path):
        """Extracts the list of dependencies from an RPM file."""
        chroot_path = self._resolve_chroot_path(rpm_path)
        if chroot_path:
            self.buildroot.root_log.debug(f"[SBOM] Using chroot-native dependencies for: {chroot_path}")
            return self._get_rpm_dependencies_chroot(chroot_path)

        self.buildroot.root_log.debug(f"[SBOM] Using host-native dependencies for: {rpm_path}")
        return self._get_rpm_dependencies_native(rpm_path)

    def _get_rpm_dependencies_chroot(self, chroot_rpm_path):
        """Extracts dependencies using rpm -qpR inside the chroot."""
        try:
            cmd = ["rpm", "-qpR", chroot_rpm_path]
            output, _ = self.buildroot.doChroot(
                cmd, shell=False, returnOutput=True, printOutput=False
            )
            return output.splitlines() if output else []
        except Exception:
            return []

    def _get_rpm_dependencies_native(self, rpm_path):
        """Extracts dependencies using native host bindings (fallback)."""
        # pylint: disable=no-member
        try:
            ts = rpm.TransactionSet()
            with open(rpm_path, "rb") as f:
                hdr = ts.hdrFromFdno(f.fileno())

            requirements = hdr[rpm.RPMTAG_REQUIRENAME]
            if not requirements:
                return []

            return [r.decode('utf-8', 'replace') if isinstance(r, bytes) else str(r) for r in requirements]
        except Exception:  # pylint: disable=broad-exception-caught
            self.buildroot.root_log.debug(f"Failed to extract dependencies via native bindings for {rpm_path}")
            return []

    def get_rpm_signature(self, rpm_path):
        """Extracts the GPG signature of an RPM file."""
        chroot_path = self._resolve_chroot_path(rpm_path)
        if chroot_path:
            self.buildroot.root_log.debug(f"[SBOM] Using chroot-native signature query for: {chroot_path}")
            return self._get_rpm_signature_chroot(chroot_path)

        self.buildroot.root_log.debug(f"[SBOM] Using host-native signature query for: {rpm_path}")
        return self._get_rpm_signature_host(rpm_path)

    def _get_rpm_signature_chroot(self, chroot_rpm_path):
        """Extracts signature using rpm inside the chroot."""
        try:
            # Try to get it via queryformat first
            cmd = ["rpm", "-qp", "--queryformat", "%{SIGPGP:pgpsig} %{SIGGPG:pgpsig}", chroot_rpm_path]
            output, _ = self.buildroot.doChroot(
                cmd, shell=False, returnOutput=True, printOutput=False
            )
            sig = output.strip() if output else ""
            if sig and sig != "(none) (none)" and sig != "(none)":
                return sig.replace("(none)", "").strip()

            # Fallback to rpm -qip
            cmd = ["rpm", "-qip", chroot_rpm_path]
            output, _ = self.buildroot.doChroot(
                cmd, shell=False, returnOutput=True, printOutput=False
            )
            if output:
                for line in output.splitlines():
                    if "Signature" in line and ":" in line:
                        sig_val = line.split(":", 1)[1].strip()
                        if sig_val and sig_val != "(none)":
                            return sig_val
            return None
        except Exception:
            return None

    def _get_rpm_signature_host(self, rpm_path):
        """Extracts signature using host tools (fallback)."""
        try:
            # Query format for signatures
            cmd = ["rpm", "-qp", "--queryformat", "%{SIGPGP:pgpsig} %{SIGGPG:pgpsig}", rpm_path]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True)
            sig = result.stdout.strip()
            if sig and sig != "(none) (none)" and sig != "(none)":
                return sig.replace("(none)", "").strip()

            # Second try via -qip
            cmd = ["rpm", "-qip", rpm_path]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True)
            for line in result.stdout.splitlines():
                if "Signature" in line and ":" in line:
                    sig_val = line.split(":", 1)[1].strip()
                    if sig_val and sig_val != "(none)":
                        return sig_val
            return None
        except Exception:
            return None


    def hash_file(self, file_path):
        """Calculates the SHA256 hash of a file."""
        sha256 = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256.update(chunk)
            return sha256.hexdigest()
        # pylint: disable=broad-exception-caught
        except Exception as e:
            self.buildroot.root_log.debug(f"Failed to hash file {file_path}: {e}")
            return None

    def extract_source_files_from_srpm(self, src_rpm_path):
        """Extracts metadata for source files from a source RPM without full extraction."""
        # pylint: disable=no-member
        self.buildroot.root_log.debug(f"Extracting source metadata from source RPM: {src_rpm_path}")
        source_files = []
        if not os.path.isfile(src_rpm_path):
            return source_files
        try:
            ts = rpm.TransactionSet()
            with open(src_rpm_path, "rb") as f:
                hdr = ts.hdrFromFdno(f.fileno())

            basenames = hdr[rpm.RPMTAG_BASENAMES]
            digests = hdr[rpm.RPMTAG_FILEDIGESTS]

            # Create a set for quick lookup of signature files
            file_set = set(basenames)

            for filename, sha256 in zip(basenames, digests):
                if filename.endswith(".spec"):
                    continue

                signature = None
                if filename.endswith(".asc") or filename.endswith(".sig"):
                    signature = "File is a signature file"
                else:
                    for ext in [".asc", ".sig"]:
                        if filename + ext in file_set:
                            signature = f"GPG signature file exists: {filename}{ext}"
                            break

                source_files.append({
                    "filename": filename,
                    "sha256": sha256,
                    "digital_signature": signature
                })
        except Exception as e:
            self.buildroot.root_log.debug(f"Failed to extract source metadata from {src_rpm_path}: {e}")

        return source_files



    def parse_spec_file(self, spec_path):
        """Parses a spec file to extract metadata and source/patch files using the specfile library."""
        self.buildroot.root_log.debug(f"[SBOM] Parsing spec file: {spec_path}")
        
        sources = []
        metadata = {
            "name": "",
            "version": "",
            "release": "",
            "license": "",
            "build_requires": [],
            "requires": []
        }

        if not os.path.isfile(spec_path):
            self.buildroot.root_log.debug(f"Spec file not found: {spec_path}")
            return metadata, sources
        try:
            chroot_spec_path = self._from_chroot_path(spec_path) or spec_path
            # Use rpmspec --parse inside the build chroot to ensure macro expansion
            # matches the build environment exactly.
            cmd = ["rpmspec", "--parse", chroot_spec_path]
            result, _ = self.buildroot.doChroot(
                cmd, shell=False, returnOutput=True, printOutput=False
            )

            if not result:
                # If doChroot returned empty, try reading local spec as fallback
                try:
                    with open(spec_path, 'r', encoding='utf-8') as f:
                        result = f.read()
                except Exception:
                    return metadata, sources

            try:
                from specfile import Specfile
                # Use specfile to parse the expanded content
                spec = Specfile(content=result, sourcedir=os.path.dirname(spec_path))


                # Extract canonical metadata
                metadata.update({
                    "name": spec.expanded_name,
                    "version": spec.expanded_version,
                    "release": spec.expanded_release,
                    "license": spec.expanded_license,
                })
                
                # Extract BuildRequires and Requires from headers
                try:
                    br = spec.rpm_spec.sourceHeader[rpm.RPMTAG_REQUIRENAME]
                    metadata["build_requires"] = [
                        r.decode('utf-8', 'replace') if isinstance(r, bytes) else str(r) 
                        for r in br
                    ] if br else []
                except (AttributeError, KeyError):
                    metadata["build_requires"] = []
                    
                try:
                    r = spec.rpm_spec.packages[0].header[rpm.RPMTAG_REQUIRENAME]
                    metadata["requires"] = [
                        req.decode('utf-8', 'replace') if isinstance(req, bytes) else str(req) 
                        for req in r
                    ] if r else []
                except (AttributeError, KeyError, IndexError):
                    metadata["requires"] = []

                # Extract both sources and patches from the spec object model
                all_locs = []
                with spec.sources() as spec_sources:
                    all_locs.extend(s.location for s in spec_sources if s.location)
                with spec.patches() as spec_patches:
                    all_locs.extend(p.location for p in spec_patches if p.location)

                for loc in all_locs:
                    filename, _, hash_value = loc.partition('#')
                    actual_filename = os.path.basename(filename)
                    build_dir = os.path.dirname(spec_path)
                    sources_dir = os.path.join(os.path.dirname(build_dir), "SOURCES")
                    file_path = os.path.join(sources_dir, actual_filename)

                    actual_hash = None
                    if os.path.isfile(file_path):
                        actual_hash = self.rpm_helper.hash_file(file_path)
                    elif hash_value:
                        actual_hash = hash_value

                    signature = (
                        self.get_file_signature(file_path) if os.path.isfile(file_path) else None
                    )

                    sources.append({
                        "filename": actual_filename,
                        "sha256": actual_hash,
                        "digital_signature": signature
                    })
                self.buildroot.root_log.debug(f"Extracted metadata {metadata} and {len(sources)} source/patch files from spec")
                
                # Double check we actually got metadata
                if not metadata.get("name"):
                    raise ValueError("Empty metadata from Specfile")
                    
            except Exception as e:
                self.buildroot.root_log.debug(f"[SBOM] FALLBACK: Specfile library failed for {spec_path}, trying regex: {e}")
                
                # Ensure result is a string for regex
                content = str(result) if result else ""
                
                # Fallback to simple regex parsing of the expanded result
                name_match = (re.search(r'^Name:\s+(.+)$', content, re.MULTILINE) or 
                              re.search(r'^name\s*:\s*(.+)$', content, re.IGNORECASE | re.MULTILINE))
                version_match = (re.search(r'^Version:\s+(.+)$', content, re.MULTILINE) or
                                 re.search(r'^version\s*:\s*(.+)$', content, re.IGNORECASE | re.MULTILINE))
                release_match = (re.search(r'^Release:\s+(.+)$', content, re.MULTILINE) or
                                 re.search(r'^release\s*:\s*(.+)$', content, re.IGNORECASE | re.MULTILINE))
                license_match = (re.search(r'^License:\s+(.+)$', content, re.MULTILINE) or
                                 re.search(r'^license\s*:\s*(.+)$', content, re.IGNORECASE | re.MULTILINE))
                
                metadata["name"] = name_match.group(1).strip() if name_match else ""
                metadata["version"] = version_match.group(1).strip() if version_match else ""
                metadata["release"] = release_match.group(1).strip() if release_match else ""
                metadata["license"] = license_match.group(1).strip() if license_match else ""
                
                # Simple source/patch extraction from expanded spec
                source_matches = re.finditer(r'^(Source|Patch)\d*:\s+(.+)$', content, re.MULTILINE)
                for sm in source_matches:
                    loc = sm.group(2).strip()
                    filename = os.path.basename(loc.partition('#')[0])
                    # Avoid duplicates
                    if not any(s['filename'] == filename for s in sources):
                        sources.append({
                            "filename": filename,
                            "sha256": None,
                            "digital_signature": None
                        })
        except Exception as e:
            self.buildroot.root_log.debug(f"Failed to parse spec file {spec_path}: {e}")
            self.buildroot.root_log.debug(traceback.format_exc())

        return metadata, sources

    def detect_chroot_distribution(self):
        """Detects the distribution ID (e.g., 'fedora', 'centos', 'rhel') from inside the chroot."""
        try:
            import distro
            try:
                distro_id = distro.id(root_dir=self.buildroot.rootdir)
            except (TypeError, AttributeError):
                # Fallback for older python-distro versions (<1.6.0)
                os_release = os.path.join(self.buildroot.rootdir, "etc/os-release")
                distro_id = "unknown"
                if os.path.isfile(os_release):
                    with open(os_release, 'r') as f:
                        for line in f:
                            if line.startswith("ID="):
                                distro_id = line.split("=")[1].strip().strip('"').strip("'")
                                break
            
            if distro_id:
                return distro_id.lower()
            return "unknown"
        except Exception as e:
            self.buildroot.root_log.debug(f"Failed to detect chroot distribution: {e}")
            return "unknown"

    def get_build_toolchain_packages(self):
        """Returns the list of packages installed in the build toolchain
        with detailed signature information collected in a single batch query."""
        try:
            fields = [
                "%{NAME}", "%{VERSION}-%{RELEASE}", "%{ARCH}", "%{LICENSE}",
                "%{BUILDTIME}", "%{RSAHEADER:pgpsig}", "%{DSAHEADER:pgpsig}",
                "%{SIGGPG:pgpsig}", "%{SIGPGP:pgpsig}", "%{SHA256HEADER}",
                "%{SOURCERPM}"
            ]
            query = "|".join(fields) + "\n"
            cmd = ["rpm", "-qa", "--qf", query]
            output, _ = self.buildroot.doChroot(
                cmd, shell=False, returnOutput=True, printOutput=False
            )
            
            packages = []
            cpe_vendor_default = self.detect_chroot_distribution() or "unknown"

            for line in output.splitlines():
                parts = line.split("|")
                if len(parts) < 6:
                    continue
                
                package_name = parts[0].strip()
                package_version = parts[1].strip()
                package_arch = parts[2].strip()
                package_license = parts[3].strip()
                build_time = parts[4].strip()
                
                raw_sig = None
                for sig_candidate in parts[5:9]:
                    sig_candidate = sig_candidate.strip()
                    if sig_candidate and sig_candidate != "(none)":
                        raw_sig = sig_candidate
                        break

                package_checksum = parts[9].strip() if len(parts) > 9 else None
                if package_checksum == "(none)":
                    package_checksum = None
                
                source_rpm = parts[10].strip() if len(parts) > 10 else None
                if source_rpm == "(none)":
                    source_rpm = None

                if (
                    package_name.startswith('gpg-pubkey') or
                    package_name == '(none)' or
                    not package_name
                ):
                    continue

                digital_signature = {
                    "signature_type": "unsigned",
                    "signature_key": None,
                    "signature_date": None,
                    "signature_algorithm": None,
                    "signature_valid": False,
                    "raw_signature_data": raw_sig,
                    "build_date": None
                }

                if raw_sig:
                    self._parse_signature_data(raw_sig, digital_signature)

                if build_time and build_time.isdigit():
                    try:
                        dt = datetime.fromtimestamp(int(build_time), tz=timezone.utc)
                        digital_signature["build_date"] = dt.isoformat()
                    except (ValueError, TypeError, OverflowError):
                        pass

                cpe = self.generate_cpe(package_name, package_version, vendor=cpe_vendor_default)

                packages.append({
                    "name": package_name,
                    "version": package_version,
                    "arch": package_arch,
                    "licenseDeclared": package_license,
                    "digital_signature": digital_signature,
                    "sourcerpm": source_rpm,
                    "cpe": cpe,
                    "checksum": package_checksum
                })
            
            self.buildroot.root_log.debug(f"Found {len(packages)} build toolchain packages")
            return packages
        except Exception as e:
            self.buildroot.root_log.debug(f"Failed to get build environment packages: {e}")
            return []

    def get_distribution(self):
        """Detects the distribution from the chroot environment (human readable)."""
        try:
            os_release = os.path.join(self.buildroot.rootdir, "etc/os-release")
            distro_name = "Unknown"
            version = ""
            if os.path.isfile(os_release):
                with open(os_release, 'r') as f:
                    for line in f:
                        if line.startswith("NAME="):
                            distro_name = line.strip().split("=", 1)[1].strip('"')
                        elif line.startswith("VERSION_ID="):
                            version = line.strip().split("=", 1)[1].strip('"')
            if distro_name and version:
                return f"{distro_name} {version}"
            return distro_name or "Unknown"
        except OSError as e:
            return f"Unknown ({e})"




