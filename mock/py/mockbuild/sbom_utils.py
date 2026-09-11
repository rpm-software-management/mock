# -*- coding: utf-8 -*-
# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# SPDX-License-Identifier: GPL-2.0-or-later
# Written by Scott R. Shinn <scott@atomicorp.com>
# Copyright (C) 2026, Atomicorp, Inc.
"""
Utility functions for SBOM generation.

This module is a library (not a plugin).  Prefer host/bootstrap RPM via
doOutChroot() — same pattern as package_state and buildroot_lock — rather than
running rpm inside the target buildroot with doChroot().
"""

import os
import re
import subprocess
import hashlib
import json
import rpm
from datetime import datetime, timezone

# RPM PGPHASHALGO_* / FILEDIGESTALGO values → SPDX/CycloneDX algorithm names.
_FILE_DIGEST_ALGOS = {
    1: "MD5",
    2: "SHA1",
    8: "SHA256",
    9: "SHA384",
    10: "SHA512",
    11: "SHA224",
    12: "SHA3-256",
    14: "SHA3-512",
}

_SHA256_HEX_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def file_digest_algo_name(algo):
    """Map RPMTAG_FILEDIGESTALGO integer to a digest algorithm name."""
    try:
        return _FILE_DIGEST_ALGOS.get(int(algo))
    except (TypeError, ValueError):
        return None


def is_sha256_hex(value):
    """Return True if value is a 64-character hex SHA-256 digest."""
    return bool(value and _SHA256_HEX_RE.match(str(value).strip()))


def nevra_key(name, version, release=None, arch=None, epoch=None):
    """Build a NEVRA identity key shared by lock files and toolchain packages.

    Toolchain packages often store version as ``V-R`` with release unset;
    lock entries keep version and release separate.
    """
    if epoch in (None, "", "(none)", "0", 0):
        epoch_part = ""
    else:
        epoch_part = f"{epoch}:"
    version = version or ""
    if release not in (None, "", "(none)"):
        vr = f"{version}-{release}"
    else:
        vr = version
    return f"{name}-{epoch_part}{vr}.{arch or ''}"


def resolve_rpm_dependency(dependency_string, name_map, provides_map=None):
    """Map a raw RPM Requires string to a package identity in name/provides maps.

    Args:
        dependency_string: e.g. ``bash >= 4.0``, ``libc.so.6()(64bit)``, ``config(bash)``.
        name_map: lowercased package name → target ref (bom-ref or SPDXID).
        provides_map: lowercased capability → target ref (optional).

    Returns:
        The mapped ref, or None if unresolved.
    """
    if not dependency_string:
        return None
    clean_dep = dependency_string.strip()
    if not clean_dep:
        return None

    provides_map = provides_map or {}

    def _lookup(token):
        if not token:
            return None
        key = token.lower()
        return provides_map.get(key) or name_map.get(key)

    # Strip RPM rich/file capability suffixes: libc.so.6()(64bit) → libc.so.6
    bare = clean_dep.split("(", 1)[0].strip() if "(" in clean_dep else clean_dep

    if " " in clean_dep or clean_dep.startswith("config("):
        pkg_name = clean_dep.split()[0].strip()
        hit = _lookup(pkg_name) or _lookup(pkg_name.split("(", 1)[0])
        if hit:
            return hit
        if clean_dep.startswith("config(") and ")" in clean_dep:
            inner_name = clean_dep[7:clean_dep.find(")")]
            return _lookup(inner_name)
        return None

    return _lookup(clean_dep) or _lookup(bare)


def should_include_rpm_file(file_path, include_debug_files=False, include_man_pages=True):
    """Shared file filter for CycloneDX and SPDX file components."""
    if not include_debug_files:
        if (
            "/usr/lib/debug/" in file_path
            or "/usr/src/debug/" in file_path
            or file_path.endswith(".debug")
            or ".build-id" in file_path
        ):
            return False

    if not include_man_pages:
        if (
            "/usr/share/man/" in file_path
            or "/usr/share/info/" in file_path
            or (file_path.endswith(".gz") and "/man" in file_path)
        ):
            return False

    return True


class RpmQueryHelper:
    # pylint: disable=broad-exception-caught
    """Helper class for querying RPM metadata."""

    def __init__(self, buildroot):
        """Initializes the helper with a buildroot for doOutChroot access."""
        self.buildroot = buildroot
        self._metadata_cache = {}
        self._signature_cache = {}

    @staticmethod
    def _rpm_transaction_set_noverify():
        """TransactionSet that reads headers without signature/digest checks.

        Cryptographic verification is handled separately by verify_rpm_signature.
        """
        # pylint: disable=no-member,protected-access
        ts = rpm.TransactionSet()
        ts.setVSFlags(rpm._RPMVSF_NOSIGNATURES | rpm._RPMVSF_NODIGESTS)
        return ts

    def _run_out_chroot(self, cmd, shell=False, with_stderr=False):
        """Run a command on the host or in the bootstrap chroot (not the target).

        Args:
            cmd: Command list (or string when shell=True).
            shell: Whether to run via the shell.
            with_stderr: When True, merge stderr into the returned output text
                (needed for ``rpm --checksig`` diagnostics that may land on
                stderr). Default False so rpm query parsers stay stdout-only.
        """
        if hasattr(self.buildroot, "doOutChroot"):
            return self.buildroot.doOutChroot(
                cmd, shell=shell, returnOutput=True, printOutput=False,
                returnStderr=with_stderr,
            )
        # Standalone / test contexts without a full Buildroot
        env = os.environ.copy()
        env["LC_ALL"] = "C"
        result = subprocess.run(
            cmd,
            shell=shell,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            text=True,
            env=env,
        )
        output = result.stdout or ""
        if with_stderr and result.stderr:
            output = (output + "\n" + result.stderr) if output else result.stderr
        return output, result.returncode

    def _chroot_root(self):
        """Return the host path to the target chroot root, or None if unset."""
        if hasattr(self.buildroot, "make_chroot_path"):
            path = self.buildroot.make_chroot_path()
            if path:
                return path
        return getattr(self.buildroot, "rootdir", None) or None

    def _usable_buildroot(self, chrootpath=None):
        """True when chrootpath is a real Mock buildroot (never host '/')."""
        path = chrootpath if chrootpath is not None else self._chroot_root()
        if not path:
            return False
        try:
            if os.path.realpath(path) == "/":
                return False
        except OSError:
            return False
        return os.path.isdir(path)

    def path_stays_in_chroot(self, path):
        """True when ``realpath(path)`` stays under the target chroot root.

        Used to refuse host-escape via symlinks planted in SPECS/SOURCES/originals.
        When no usable chroot is configured (standalone CLI without ``--root``),
        returns True so callers are not blocked.
        """
        if not path:
            return False
        root = self._chroot_root()
        if not self._usable_buildroot(root):
            return True
        try:
            real = os.path.realpath(path)
            root_real = os.path.realpath(root)
        except OSError:
            return False
        if real == root_real:
            return True
        prefix = root_real if root_real.endswith(os.sep) else root_real + os.sep
        return real.startswith(prefix)

    def open_chroot_file(self, path, mode="rb"):
        """Open a chroot-resident file without following a final-component symlink.

        Raises OSError when the path resolves outside the chroot or the final
        path component is a symlink (``O_NOFOLLOW``).
        """
        if not self.path_stays_in_chroot(path):
            raise OSError(f"Refusing path outside chroot: {path}")
        if os.path.islink(path):
            raise OSError(f"Refusing symlink path: {path}")
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        # Write modes are not used for prebuild forensic reads.
        if "w" in mode or "a" in mode or "+" in mode:
            raise ValueError("open_chroot_file only supports read modes")
        fd = os.open(path, flags)
        if "b" in mode:
            return os.fdopen(fd, mode)
        return os.fdopen(fd, mode, encoding="utf-8", errors="replace")

    def host_path(self, path):
        """Resolve a path to a host-visible filesystem location.

        Accepts either a host path or a chroot-relative path and returns a path
        that host/bootstrap tools (and python-rpm) can open directly.

        When a usable buildroot is configured, chroot-relative paths (e.g.
        ``/etc/passwd``, ``/builddir/build/...``) are resolved under the chroot
        first so they cannot silently bind to host files of the same name.
        Absolute paths already under ``rootdir`` or ``resultdir`` are returned
        as-is.
        """
        if not path:
            return path

        root = self._chroot_root()
        resultdir = getattr(self.buildroot, "resultdir", None)
        usable = self._usable_buildroot(root)

        # Already a host path under the chroot or result dir.
        if usable:
            try:
                real = os.path.realpath(path)
                root_real = os.path.realpath(root)
                if real == root_real or real.startswith(
                    root_real if root_real.endswith(os.sep) else root_real + os.sep
                ):
                    return path
            except OSError:
                pass
        if resultdir:
            try:
                real = os.path.realpath(path)
                result_real = os.path.realpath(resultdir)
                if real == result_real or real.startswith(
                    result_real if result_real.endswith(os.sep)
                    else result_real + os.sep
                ):
                    return path
            except OSError:
                pass

        # Prefer chroot resolution when a buildroot is available.
        if usable and hasattr(self.buildroot, "make_chroot_path"):
            candidate = self.buildroot.make_chroot_path(path.lstrip("/"))
            if candidate and os.path.exists(candidate):
                return candidate

        # Resultdir artifacts may also exist under the chroot build tree
        if resultdir and path.startswith(resultdir):
            filename = os.path.basename(path)
            # Honor a non-default chroothome (Buildroot.builddir is derived
            # from config_opts['chroothome'] + "/build").
            build_base = (
                getattr(self.buildroot, "builddir", None) or "/builddir/build"
            ).lstrip("/")
            search_paths = [
                os.path.join(build_base, sub)
                for sub in (
                    "RPMS", "RPMS/x86_64", "RPMS/noarch", "SRPMS", "SOURCES",
                )
            ]
            for search_path in search_paths:
                if hasattr(self.buildroot, "make_chroot_path"):
                    candidate = self.buildroot.make_chroot_path(search_path, filename)
                else:
                    if not root:
                        continue
                    candidate = os.path.join(root, search_path, filename)
                if candidate and os.path.exists(candidate):
                    return candidate

        # No usable buildroot: allow existing host paths (standalone CLI).
        if not usable and (os.path.isfile(path) or os.path.isdir(path)):
            return path

        return path

    def generate_purl(self, package_name, version, distro_obj=None, arch=None,
                      epoch=None, distro_version=None):
        """Generates a Package URL (PURL) for an RPM package.

        Format: pkg:rpm/<namespace>/<name>@<version>?arch=&epoch=&distro=
        Qualifier/path fields are sanitized so raw metadata cannot inject
        extra PURL separators (``?``, ``&``, ``=``, ``#``).
        """
        clean_name = self._purl_token(package_name)
        namespace = self._purl_token(distro_obj) if distro_obj else "rpm"
        clean_version = self._purl_token(version, allow_empty=False) or "unknown"
        purl = f"pkg:rpm/{namespace}/{clean_name}@{clean_version}"
        qualifiers = []
        if arch and arch != "(none)":
            qualifiers.append(f"arch={self._purl_token(arch)}")
        if epoch not in (None, "", "(none)", "0"):
            qualifiers.append(f"epoch={self._purl_token(epoch)}")
        if distro_obj and distro_version:
            distro_q = self._purl_token(f"{distro_obj}-{distro_version}")
            qualifiers.append(f"distro={distro_q}")
        elif distro_obj and distro_obj != "rpm":
            qualifiers.append(f"distro={self._purl_token(distro_obj)}")
        if qualifiers:
            purl += "?" + "&".join(qualifiers)
        return purl

    @staticmethod
    def _purl_token(value, allow_empty=True):
        """Sanitize a PURL path or qualifier component."""
        if value is None:
            return "" if allow_empty else None
        text = str(value).strip()
        # Replace characters that would inject extra PURL structure.
        for bad in ("?", "#", "&", "=", "@", ":"):
            text = text.replace(bad, "-")
        text = re.sub(r'[^a-zA-Z0-9.+_~-]', '-', text)
        text = re.sub(r'-{2,}', '-', text).strip('-')
        if not text and not allow_empty:
            return None
        return text or "unknown"

    def generate_cpe(self, package_name, package_version, vendor=None):
        """Generate a heuristic CPE 2.3 identifier.

        These CPEs are fabricated from package metadata and are NOT looked up
        against the NVD dictionary. Callers must label them as heuristic.
        Returns (cpe_string, confidence) where confidence is 'heuristic'.
        """
        if not vendor or vendor == "(none)":
            vendor = "unknown"

        vendor = self._cpe_token(vendor)
        product = self._cpe_token(package_name)
        version = str(package_version or "").strip()
        if '-' in version:
            version = version.split('-')[0]
        version = self._cpe_token(version) if version else "unknown"

        cpe = f"cpe:2.3:a:{vendor}:{product}:{version}:*:*:*:*:*:*:*:*"
        return cpe, "heuristic"

    @staticmethod
    def _cpe_token(value):
        """Sanitize a CPE 2.3 field (no colons — they shift field boundaries)."""
        text = str(value or "").strip().lower()
        text = text.replace(":", "_").replace("*", "_").replace("?", "_")
        text = re.sub(r'[^a-zA-Z0-9._-]', '_', text)
        return text or "unknown"

    def _empty_signature_info(self):
        """Return a blank signature info dict with evidence-backed defaults."""
        return {
            "signature_type": "unsigned",
            "signature_key": None,
            "signature_date": None,
            "signature_algorithm": None,
            # Tri-state: verified | present-unverified | unsigned
            "signature_status": "unsigned",
            # Kept for backwards compatibility; True only when cryptographically verified
            "signature_valid": False,
            "raw_signature_data": None,
            "build_date": None,
        }

    def parse_signature_data(self, sig_data, signature_info=None):
        """Parse a raw RPM signature string without claiming validity.

        Presence of a signature string only proves the package is signed
        (status: present-unverified). Cryptographic verification is separate.
        """
        if signature_info is None:
            signature_info = self._empty_signature_info()

        if not sig_data or sig_data in ("(none)", ""):
            signature_info["signature_type"] = "unsigned"
            signature_info["signature_status"] = "unsigned"
            signature_info["signature_valid"] = False
            return signature_info

        signature_info["signature_type"] = "GPG"
        signature_info["signature_status"] = "present-unverified"
        signature_info["signature_valid"] = False
        signature_info["raw_signature_data"] = sig_data

        if "RSA/SHA256" in sig_data:
            signature_info["signature_algorithm"] = "RSA/SHA256"
        elif "DSA/SHA1" in sig_data:
            signature_info["signature_algorithm"] = "DSA/SHA1"
        elif "ECDSA/SHA256" in sig_data:
            signature_info["signature_algorithm"] = "ECDSA/SHA256"
        elif "Ed25519/SHA256" in sig_data:
            signature_info["signature_algorithm"] = "Ed25519/SHA256"

        key_id_match = re.search(r'Key ID ([0-9a-fA-F]+)', sig_data)
        if key_id_match:
            signature_info["signature_key"] = key_id_match.group(1)

        date_match = re.search(
            r'([A-Za-z]{3} [A-Za-z]{3}\s+\d{1,2} \d{2}:\d{2}:\d{2} \d{4})',
            sig_data
        )
        if date_match:
            signature_info["signature_date"] = date_match.group(1)

        return signature_info

    def verify_rpm_signature(self, rpm_path):
        """Cryptographically verify an RPM signature via rpm/rpmkeys --checksig.

        Returns a signature_info dict with signature_status set to one of:
        verified, present-unverified, or unsigned.
        """
        host_path = self.host_path(rpm_path)
        cache_key = host_path or rpm_path
        if cache_key in self._signature_cache:
            return dict(self._signature_cache[cache_key])

        info = self._empty_signature_info()
        if not os.path.isfile(host_path):
            self._signature_cache[cache_key] = dict(info)
            return info

        # Header signature string is best-effort metadata (key id, algorithm).
        # Always run rpm --checksig below — extraction failures must not mark
        # a signed RPM as unsigned.
        raw = self.get_rpm_signature(host_path)
        self.parse_signature_data(raw, info)

        chrootpath = self._chroot_root()
        # Prefer verifying against the target chroot's keyring when available.
        cmd = ["rpm", "--checksig", host_path]
        if chrootpath and chrootpath != "/":
            cmd = ["rpm", "--root", chrootpath, "--checksig", host_path]

        try:
            output, rc = self._run_out_chroot(cmd, with_stderr=True)
            text = (output or "").strip()
            text_l = text.lower()
            # rpm --checksig prints "digests signatures OK" on success.
            if rc == 0 and ("signatures ok" in text_l or "signature ok" in text_l):
                info["signature_status"] = "verified"
                info["signature_valid"] = True
            elif (
                "signature" in text_l
                or "nokey" in text_l
                or info["signature_status"] != "unsigned"
            ):
                # Header and/or checksig indicate a signature is present, but
                # it was not cryptographically verified (NOKEY / NOT OK / …).
                info["signature_status"] = "present-unverified"
                info["signature_valid"] = False
            # else: truly unsigned — leave status from parse_signature_data
            if text:
                info["raw_signature_data"] = info.get("raw_signature_data") or text
        except Exception as exc:
            self.buildroot.root_log.warning(
                "Signature verification failed for %s: %s", host_path, exc
            )
            if info["signature_status"] != "unsigned":
                info["signature_status"] = "present-unverified"
                info["signature_valid"] = False

        self._signature_cache[cache_key] = dict(info)
        return info

    def get_rpm_metadata(self, rpm_path):
        """Extracts metadata from an RPM file via host-visible path + python-rpm."""
        host_path = self.host_path(rpm_path)
        cache_key = host_path or rpm_path
        if cache_key in self._metadata_cache:
            return dict(self._metadata_cache[cache_key])

        if not os.path.isfile(host_path):
            self.buildroot.root_log.debug("RPM file not found: %s", rpm_path)
            return {}

        self.buildroot.root_log.debug(
            "[SBOM] Using host-native analysis for: %s", host_path
        )
        metadata = self._get_rpm_metadata_native(host_path)
        # Only cache successful parses so a transient failure can be retried.
        if metadata:
            self._metadata_cache[cache_key] = dict(metadata)
        return metadata

    def _get_rpm_metadata_native(self, rpm_path):
        """Extracts metadata using native host bindings."""
        # pylint: disable=no-member
        try:
            ts = self._rpm_transaction_set_noverify()
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
            self.buildroot.root_log.debug(
                "Failed to extract metadata via native bindings for %s", rpm_path
            )
            return {}



    def get_rpm_file_info(self, rpm_path):
        """Extracts file hashes, ownership, and permissions from an RPM file."""
        host_path = self.host_path(rpm_path)
        if not os.path.isfile(host_path):
            return {}
        self.buildroot.root_log.debug("[SBOM] Using host-native file info for: %s", host_path)
        return self._get_rpm_file_info_native(host_path)

    def _get_rpm_file_info_native(self, rpm_path):
        """Extracts file information using native host bindings."""
        # pylint: disable=no-member
        file_info = {}
        try:
            ts = self._rpm_transaction_set_noverify()
            # pylint: disable=protected-access
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

                owner = fileusernames[i]
                if isinstance(owner, bytes):
                    owner = owner.decode('utf-8', 'replace')
                group = filegroupnames[i]
                if isinstance(group, bytes):
                    group = group.decode('utf-8', 'replace')
                algo_name = file_digest_algo_name(algo)
                entry = {
                    "hash": digest if digest else None,
                    "algo": algo,
                    "digest_algorithm": algo_name,
                    "permissions": f"0{filemodes[i]:o}",
                    "owner": owner,
                    "group": group,
                }
                if algo_name == "SHA256" and digest:
                    entry["sha256"] = digest
                elif algo_name == "SHA1" and digest:
                    entry["sha1"] = digest
                elif algo_name == "MD5" and digest:
                    entry["md5"] = digest
                file_info[filename] = entry
            return file_info
        except Exception:
            self.buildroot.root_log.debug(
                "Native RPM file-info extraction returned empty for %s", rpm_path
            )
            return {}

    def get_rpm_dependencies(self, rpm_path):
        """Extracts the list of dependencies from an RPM file."""
        host_path = self.host_path(rpm_path)
        if not os.path.isfile(host_path):
            return []
        self.buildroot.root_log.debug("[SBOM] Using host-native dependencies for: %s", host_path)
        return self._get_rpm_dependencies_native(host_path)

    def _get_rpm_dependencies_native(self, rpm_path):
        """Extracts dependencies using native host bindings."""
        # pylint: disable=no-member
        try:
            ts = self._rpm_transaction_set_noverify()
            with open(rpm_path, "rb") as f:
                hdr = ts.hdrFromFdno(f.fileno())

            requirements = hdr[rpm.RPMTAG_REQUIRENAME]
            if not requirements:
                return []

            return [r.decode('utf-8', 'replace') if isinstance(r, bytes) else str(r) for r in requirements]
        except Exception:  # pylint: disable=broad-exception-caught
            self.buildroot.root_log.debug(
                "Failed to extract dependencies via native bindings for %s", rpm_path
            )
            return []

    def get_rpm_provides(self, rpm_path):
        """Extract Provides capabilities from an RPM file."""
        host_path = self.host_path(rpm_path)
        if not os.path.isfile(host_path):
            return []
        return self._get_rpm_provides_native(host_path)

    def _get_rpm_provides_native(self, rpm_path):
        """Extract Provides using native host bindings."""
        # pylint: disable=no-member
        try:
            ts = self._rpm_transaction_set_noverify()
            with open(rpm_path, "rb") as handle:
                hdr = ts.hdrFromFdno(handle.fileno())
            provides = hdr[rpm.RPMTAG_PROVIDENAME]
            if not provides:
                return []
            return [
                p.decode("utf-8", "replace") if isinstance(p, bytes) else str(p)
                for p in provides
            ]
        except Exception:  # pylint: disable=broad-exception-caught
            self.buildroot.root_log.debug(
                "Failed to extract Provides via native bindings for %s", rpm_path
            )
            return []

    def get_installed_provides_map(self, package_names=None):
        """Map installed capability names to providing package names.

        Uses ``rpm -qa`` with array formatting so each Provide is paired with
        its package name. Optional ``package_names`` limits which providers are
        retained (lowercased set).
        """
        chrootpath = self._chroot_root()
        if not self._usable_buildroot(chrootpath):
            return {}
        cmd = ["rpm", "-qa", "--qf", "[%{=NAME}\t%{PROVIDENAME}\n]"]
        if chrootpath and chrootpath != "/":
            cmd[1:1] = ["--root", chrootpath]
        try:
            output = self._rpm_db_executor(cmd)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self.buildroot.root_log.debug(
                "Installed Provides query failed: %s", exc
            )
            return {}

        wanted = {n.lower() for n in package_names} if package_names else None
        provides_map = {}
        for line in (output or "").splitlines():
            if "\t" not in line:
                continue
            pkg_name, capability = line.split("\t", 1)
            pkg_name = pkg_name.strip()
            capability = capability.strip()
            if not pkg_name or not capability or pkg_name.startswith("gpg-pubkey"):
                continue
            if wanted is not None and pkg_name.lower() not in wanted:
                continue
            # First provider wins; later duplicates are ignored.
            provides_map.setdefault(capability.lower(), pkg_name.lower())
            # Also index bare soname without ()(64bit) suffixes.
            bare = capability.split("(", 1)[0].strip().lower()
            if bare and bare not in provides_map:
                provides_map[bare] = pkg_name.lower()
        return provides_map

    def get_rpm_signature(self, rpm_path):
        """Extract the GPG signature description for an RPM file.

        Prefers python-rpm header tags (SIGPGP / SIGGPG) over locale-dependent
        ``rpm -qip`` text parsing.
        """
        host_path = self.host_path(rpm_path)
        if not os.path.isfile(host_path):
            return None

        # Prefer header tags via python-rpm (locale-independent)
        try:
            ts = self._rpm_transaction_set_noverify()
            with open(host_path, "rb") as handle:
                hdr = ts.hdrFromFdno(handle.fileno())
            # Binary blob presence indicates a signature; get printable form via rpm
            has_sig = False
            for tag_const in (
                getattr(rpm, "RPMTAG_SIGPGP", None),
                getattr(rpm, "RPMTAG_SIGGPG", None),
                getattr(rpm, "RPMTAG_RSAHEADER", None),
                getattr(rpm, "RPMTAG_DSAHEADER", None),
            ):
                if tag_const is None:
                    continue
                try:
                    val = hdr[tag_const]
                    if val:
                        has_sig = True
                        break
                except Exception:  # pylint: disable=broad-exception-caught
                    continue
            if has_sig:
                printable = self._get_rpm_signature_host(host_path)
                return printable or "GPG signature present"
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self.buildroot.root_log.debug(
                "python-rpm signature read failed for %s: %s", host_path, exc
            )

        return self._get_rpm_signature_host(host_path)

    def _get_rpm_signature_host(self, rpm_path):
        """Extract printable signature via host rpm queryformat (LC_ALL=C)."""
        try:
            cmd = [
                "rpm", "-qp", "--queryformat",
                "%{SIGPGP:pgpsig}|%{SIGGPG:pgpsig}|%{RSAHEADER:pgpsig}|%{DSAHEADER:pgpsig}",
                rpm_path,
            ]
            output, _ = self._run_out_chroot(cmd)
            if output:
                for part in output.strip().split("|"):
                    part = part.strip()
                    if part and part != "(none)":
                        return part
            return None
        except Exception:  # pylint: disable=broad-exception-caught
            return None


    def hash_file(self, file_path, require_in_chroot=False, algorithm="sha256"):
        """Calculates a file digest (SHA-256 by default).

        When ``require_in_chroot`` is True (prebuild SPECS/SOURCES/originals),
        refuses final-component symlinks and paths that escape the chroot.
        Result-dir RPM hashing leaves this False — resultdir is outside rootdir.

        ``algorithm`` may be ``sha256`` or ``sha1``. SHA-1 is only for SPDX
        packageVerificationCode coverage (not a security claim).
        """
        algo = (algorithm or "sha256").lower().replace("-", "")
        if algo == "sha1":
            try:
                digest = hashlib.sha1(usedforsecurity=False)
            except TypeError:
                digest = hashlib.sha1()
        else:
            digest = hashlib.sha256()
        try:
            if require_in_chroot:
                handle = self.open_chroot_file(file_path, "rb")
            else:
                handle = open(file_path, "rb")  # pylint: disable=consider-using-with
            with handle as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    digest.update(chunk)
            return digest.hexdigest()
        # pylint: disable=broad-exception-caught
        except Exception as e:
            self.buildroot.root_log.debug("Failed to hash file %s: %s", file_path, e)
            return None

    def capture_originals_input_srpm(self, originals_dir):
        """Fingerprint the chain-of-custody input SRPM under ``originals/``.

        Picks the first ``*.src.rpm`` by sorted filename for determinism.
        Returns a source-file dict (filename, sha256, digital_signature,
        source_type, role) or None if the directory is missing/empty.
        Propagates ``OSError`` so callers can log at their preferred level.
        Symlinks are skipped so a malicious SRPM cannot point hashing at a
        host path.
        """
        if not originals_dir or not os.path.isdir(originals_dir):
            return None
        if not self.path_stays_in_chroot(originals_dir):
            raise OSError(f"Refusing originals dir outside chroot: {originals_dir}")
        candidates = sorted(
            (
                entry
                for entry in os.scandir(originals_dir)
                if (not entry.is_symlink()
                    and entry.is_file(follow_symlinks=False)
                    and entry.name.endswith(".src.rpm"))
            ),
            key=lambda e: e.name,
        )
        if not candidates:
            return None
        entry = candidates[0]
        return {
            "filename": entry.name,
            "sha256": self.hash_file(entry.path, require_in_chroot=True),
            "digital_signature": self.verify_rpm_signature(entry.path),
            "source_type": "source_rpm",
            "role": "input",
        }

    def get_file_signature(self, file_path):
        """Detect a sidecar digital signature for a source/patch file."""
        try:
            for suffix in (".asc", ".sig"):
                sig_file = file_path + suffix
                if os.path.isfile(sig_file):
                    return "GPG signature file exists: " + os.path.basename(sig_file)
            if file_path.endswith(".asc") or file_path.endswith(".sig"):
                return "File is a signature file"
            return None
        except OSError as e:
            self.buildroot.root_log.debug("Failed to check signature for %s: %s", file_path, e)
            return None

    @staticmethod
    def merge_source_files(spec_sources, srpm_sources):
        """Merge SRPM header digests and signatures into spec-derived source entries."""
        if not srpm_sources:
            return list(spec_sources or [])
        if not spec_sources:
            return list(srpm_sources)

        srpm_by_name = {entry["filename"]: entry for entry in srpm_sources if entry.get("filename")}
        merged = []
        seen = set()
        for entry in spec_sources:
            filename = entry.get("filename")
            if not filename:
                continue
            srpm_entry = srpm_by_name.get(filename, {})
            merged.append({
                **entry,
                "filename": filename,
                "sha256": entry.get("sha256") or srpm_entry.get("sha256"),
                "digital_signature": (
                    entry.get("digital_signature")
                    or srpm_entry.get("digital_signature")
                ),
            })
            seen.add(filename)

        for srpm_entry in srpm_sources:
            filename = srpm_entry.get("filename")
            if filename and filename not in seen:
                merged.append(dict(srpm_entry))
        return merged

    @staticmethod
    def _source_file_signature(filename, file_set):
        """Return GPG companion-file status for a source archive or patch."""
        if filename.endswith(".asc") or filename.endswith(".sig"):
            return "File is a signature file"
        for ext in (".asc", ".sig"):
            if filename + ext in file_set:
                return f"GPG signature file exists: {filename}{ext}"
        return None

    def _extract_source_files_from_srpm_header(self, src_rpm_path):
        """Read per-file digests from an SRPM header via python-rpm.

        Honors ``RPMTAG_FILEDIGESTALGO``: only populate ``sha256`` when the
        algorithm is SHA-256; otherwise store under the correct field or omit
        rather than mislabel.
        """
        # pylint: disable=no-member
        source_files = []
        ts = self._rpm_transaction_set_noverify()
        with open(src_rpm_path, "rb") as f:
            hdr = ts.hdrFromFdno(f.fileno())

        basenames = hdr[rpm.RPMTAG_BASENAMES]
        digests = hdr[rpm.RPMTAG_FILEDIGESTS]
        try:
            algo = hdr[rpm.RPMTAG_FILEDIGESTALGO]
        except (KeyError, IndexError):
            algo = 8
        algo_name = file_digest_algo_name(algo)

        file_set = set()
        for name in basenames:
            if isinstance(name, bytes):
                name = name.decode("utf-8", "replace")
            file_set.add(name)

        for filename, digest in zip(basenames, digests):
            if isinstance(filename, bytes):
                filename = filename.decode("utf-8", "replace")
            if filename.endswith(".spec"):
                continue
            if isinstance(digest, bytes):
                digest = digest.decode("utf-8", "replace")
            entry = {
                "filename": filename,
                "digital_signature": self._source_file_signature(filename, file_set),
            }
            if digest and algo_name == "SHA256":
                entry["sha256"] = digest
            elif digest and algo_name == "SHA1":
                entry["sha1"] = digest
            elif digest and algo_name == "MD5":
                entry["md5"] = digest
            elif digest and algo_name:
                entry["digest"] = digest
                entry["digest_algorithm"] = algo_name
            source_files.append(entry)
        return source_files

    def _extract_source_files_from_srpm_cli(self, src_rpm_path):
        """Read per-file digests from an SRPM using host/bootstrap rpm."""
        source_files = []
        query_format = "[%{BASENAMES}|%{FILEDIGESTS}|%{FILEDIGESTALGO}\n]"
        try:
            output, rc = self._run_out_chroot(
                ["rpm", "-qp", "--qf", query_format, src_rpm_path]
            )
            if rc not in (0, None) or not (output or "").strip():
                return source_files
        except Exception as e:  # pylint: disable=broad-exception-caught
            self.buildroot.root_log.debug(
                "rpm query failed for %s: %s", src_rpm_path, e
            )
            return source_files

        file_set = set()
        entries = []
        algo_name = None
        for line in output.splitlines():
            parts = line.split("|")
            if len(parts) < 2:
                continue
            filename = parts[0]
            digest = parts[1]
            if len(parts) >= 3 and parts[2].strip().isdigit():
                algo_name = file_digest_algo_name(int(parts[2].strip()))
            if filename.endswith(".spec"):
                continue
            file_set.add(filename)
            entries.append((filename, digest))

        # Default to SHA-256 when FILEDIGESTALGO is absent (legacy RPMs).
        if algo_name is None:
            algo_name = "SHA256"

        for filename, digest in entries:
            entry = {
                "filename": filename,
                "digital_signature": self._source_file_signature(filename, file_set),
            }
            if digest and algo_name == "SHA256":
                entry["sha256"] = digest
            elif digest and algo_name == "SHA1":
                entry["sha1"] = digest
            elif digest and algo_name == "MD5":
                entry["md5"] = digest
            elif digest and algo_name:
                entry["digest"] = digest
                entry["digest_algorithm"] = algo_name
            source_files.append(entry)
        return source_files

    def extract_source_files_from_srpm(self, src_rpm_path):
        """Extracts metadata for source files from a source RPM without full extraction."""
        self.buildroot.root_log.debug("Extracting source metadata from source RPM: %s", src_rpm_path)
        if not os.path.isfile(src_rpm_path):
            return []

        for extractor in (
            self._extract_source_files_from_srpm_header,
            self._extract_source_files_from_srpm_cli,
        ):
            try:
                source_files = extractor(src_rpm_path)
                if source_files:
                    return source_files
            except Exception as e:
                self.buildroot.root_log.debug(
                    f"Source metadata extraction via {extractor.__name__} failed for {src_rpm_path}: {e}"
                )

        return []



    def _expand_simple_spec_macros(self, value, version=None):
        """Expand common unexpanded macros left by regex fallback parsing.

        Handles %{version}, %{dist}, and %{?dist}. Dist is derived from the
        *target chroot* os-release (e.g. .el9), not the host's RPM macros.
        """
        if not value or "%" not in str(value):
            return value
        result = str(value)
        if version:
            result = result.replace("%{version}", version)
            result = result.replace("%{VERSION}", version)

        dist = ""
        distro_id = self.detect_chroot_distribution() or ""
        ver = self.get_distribution_version() or ""
        major = ver.split(".", 1)[0] if ver else ""
        if distro_id in ("rhel", "centos", "rocky", "almalinux", "ol", "eurolinux") and major:
            dist = f".el{major}"
        elif distro_id == "fedora" and major:
            dist = f".fc{major}"

        if not dist:
            # Last resort: rpm --eval against the target chroot only (never host /)
            try:
                chrootpath = self._chroot_root()
                if self._usable_buildroot(chrootpath):
                    cmd = ["rpm", "--root", chrootpath, "--eval", "%{?dist}"]
                    out, _ = self._run_out_chroot(cmd)
                    dist = (out or "").strip()
            except Exception:  # pylint: disable=broad-exception-caught
                dist = ""

        if dist:
            result = result.replace("%{?dist}", dist)
            result = result.replace("%{dist}", dist)
        else:
            # Always expand %{?dist} (empty when unknown) so unexpanded macros
            # do not leak into package NVR strings.
            result = result.replace("%{?dist}", "")
        return result

    def _parse_spec_content_with_specfile(self, content, host_spec_path, metadata, sources):
        """Populate metadata/sources from expanded spec content via Specfile."""
        from specfile import Specfile

        spec = Specfile(content=content, sourcedir=os.path.dirname(host_spec_path))
        metadata.update({
            "name": spec.expanded_name,
            "version": spec.expanded_version,
            "release": spec.expanded_release,
            "license": spec.expanded_license,
        })
        try:
            br = spec.rpm_spec.sourceHeader[rpm.RPMTAG_REQUIRENAME]
            metadata["build_requires"] = [
                r.decode("utf-8", "replace") if isinstance(r, bytes) else str(r)
                for r in br
            ] if br else []
        except (AttributeError, KeyError):
            metadata["build_requires"] = []
        try:
            reqs = spec.rpm_spec.packages[0].header[rpm.RPMTAG_REQUIRENAME]
            metadata["requires"] = [
                req.decode("utf-8", "replace") if isinstance(req, bytes) else str(req)
                for req in reqs
            ] if reqs else []
        except (AttributeError, KeyError, IndexError):
            metadata["requires"] = []

        all_locs = []
        # Specfile's sources()/patches() return GeneratorContextManager objects
        # at runtime; pylint can't see that (E1129 false positive).
        with spec.sources() as spec_sources:  # pylint: disable=not-context-manager
            all_locs.extend(s.location for s in spec_sources if s.location)
        with spec.patches() as spec_patches:  # pylint: disable=not-context-manager
            all_locs.extend(p.location for p in spec_patches if p.location)

        for loc in all_locs:
            filename, _, hash_value = loc.partition("#")
            actual_filename = os.path.basename(filename)
            build_dir = os.path.dirname(host_spec_path)
            sources_dir = os.path.join(os.path.dirname(build_dir), "SOURCES")
            file_path = os.path.join(sources_dir, actual_filename)
            actual_hash = None
            # Refuse symlink escape from SOURCES/ into host paths.
            if (
                os.path.isfile(file_path)
                and not os.path.islink(file_path)
                and self.path_stays_in_chroot(file_path)
            ):
                actual_hash = self.hash_file(file_path, require_in_chroot=True)
            elif hash_value and is_sha256_hex(hash_value):
                actual_hash = hash_value.strip()
            signature = None
            if (
                os.path.isfile(file_path)
                and not os.path.islink(file_path)
                and self.path_stays_in_chroot(file_path)
            ):
                signature = self.get_file_signature(file_path)
            sources.append({
                "filename": actual_filename,
                "sha256": actual_hash,
                "digital_signature": signature,
            })
        if not metadata.get("name"):
            raise ValueError("Empty metadata from Specfile")

    def _parse_spec_content_with_regex(self, content, metadata, sources):
        """Regex fallback for when Specfile cannot parse the content."""
        name_match = (
            re.search(r"^Name:\s+(.+)$", content, re.MULTILINE)
            or re.search(r"^name\s*:\s*(.+)$", content, re.IGNORECASE | re.MULTILINE)
        )
        version_match = (
            re.search(r"^Version:\s+(.+)$", content, re.MULTILINE)
            or re.search(r"^version\s*:\s*(.+)$", content, re.IGNORECASE | re.MULTILINE)
        )
        release_match = (
            re.search(r"^Release:\s+(.+)$", content, re.MULTILINE)
            or re.search(r"^release\s*:\s*(.+)$", content, re.IGNORECASE | re.MULTILINE)
        )
        license_match = (
            re.search(r"^License:\s+(.+)$", content, re.MULTILINE)
            or re.search(r"^license\s*:\s*(.+)$", content, re.IGNORECASE | re.MULTILINE)
        )

        version = version_match.group(1).strip() if version_match else ""
        release = release_match.group(1).strip() if release_match else ""
        version = self._expand_simple_spec_macros(version)
        release = self._expand_simple_spec_macros(release, version=version)

        metadata["name"] = name_match.group(1).strip() if name_match else ""
        metadata["version"] = version
        metadata["release"] = release
        metadata["license"] = license_match.group(1).strip() if license_match else ""

        # Expand macros inside source/patch filenames too
        source_matches = re.finditer(
            r"^(Source|Patch)\d*:\s+(.+)$", content, re.MULTILINE
        )
        for sm in source_matches:
            loc = sm.group(2).strip()
            loc = self._expand_simple_spec_macros(loc, version=version)
            filename = os.path.basename(loc.partition("#")[0])
            if filename and not any(s["filename"] == filename for s in sources):
                sources.append({
                    "filename": filename,
                    "sha256": None,
                    "digital_signature": None,
                })

    def parse_spec_file(self, spec_path):
        """Parse a spec file for metadata and source/patch files.

        Prefers host-visible content. Tries ``rpmspec --parse`` via doOutChroot
        when useful, but always falls back to reading the host file and
        Specfile/regex parsing when bootstrap rpmspec fails (common for
        host paths that are not visible inside the bootstrap nspawn).
        """
        self.buildroot.root_log.debug("[SBOM] Parsing spec file: %s", spec_path)

        sources = []
        metadata = {
            "name": "",
            "version": "",
            "release": "",
            "license": "",
            "build_requires": [],
            "requires": [],
        }

        host_spec_path = self.host_path(spec_path)
        if not os.path.isfile(host_spec_path):
            self.buildroot.root_log.debug("Spec file not found: %s", host_spec_path)
            return metadata, sources

        # 1) Prefer reading host file first (always available for mock SPECS).
        file_content = ""
        try:
            with self.open_chroot_file(
                host_spec_path, "r"
            ) as handle:
                file_content = handle.read()
        except OSError as exc:
            self.buildroot.root_log.warning(
                "Failed to read spec file %s: %s", host_spec_path, exc
            )
            return metadata, sources

        # 2) Best-effort macro expansion via rpmspec (may fail in bootstrap).
        result = None
        try:
            cmd = ["rpmspec", "--parse", host_spec_path]
            result, rc = self._run_out_chroot(cmd)
            if rc not in (0, None) or not (result or "").strip():
                result = None
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self.buildroot.root_log.debug(
                "rpmspec --parse via doOutChroot failed for %s: %s; using host file",
                host_spec_path, exc,
            )
            result = None

        content = (result or "").strip() or file_content

        # 3) Specfile first, regex fallback second — never skip fallback on parse errors.
        try:
            self._parse_spec_content_with_specfile(
                content, host_spec_path, metadata, sources
            )
            self.buildroot.root_log.debug(
                "Extracted metadata %s and %s source/patch files from spec",
                metadata, len(sources),
            )
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self.buildroot.root_log.debug(
                "[SBOM] FALLBACK: Specfile library failed for %s, trying regex: %s",
                spec_path, exc,
            )
            sources.clear()
            self._parse_spec_content_with_regex(content, metadata, sources)
            # If expanded content still failed macros, try raw file content too
            if not metadata.get("name") and content != file_content:
                self._parse_spec_content_with_regex(file_content, metadata, sources)

        # Final safety: expand any remaining macros in name/version/release
        if metadata.get("version"):
            metadata["version"] = self._expand_simple_spec_macros(metadata["version"])
        if metadata.get("release"):
            metadata["release"] = self._expand_simple_spec_macros(
                metadata["release"], version=metadata.get("version")
            )
        for src in sources:
            src["filename"] = self._expand_simple_spec_macros(
                src.get("filename") or "", version=metadata.get("version")
            )

        return metadata, sources

    def detect_chroot_distribution(self):
        """Detects the distribution ID (e.g., 'fedora', 'centos', 'rhel') from inside the chroot."""
        if not self._usable_buildroot():
            return "unknown"
        try:
            import distro
            try:
                # distro.id() takes no arguments; root_dir support lives on
                # the LinuxDistribution class (python-distro >= 1.6.0).
                dist = distro.LinuxDistribution(root_dir=self.buildroot.rootdir)
                distro_id = dist.id()
            except (TypeError, AttributeError):
                # Fallback for older python-distro versions (<1.6.0)
                os_release = os.path.join(self.buildroot.rootdir, "etc/os-release")
                distro_id = "unknown"
                if os.path.isfile(os_release):
                    with open(os_release, 'r', encoding='utf-8') as f:
                        for line in f:
                            if line.startswith("ID="):
                                distro_id = line.split("=")[1].strip().strip('"').strip("'")
                                break

            if distro_id:
                return distro_id.lower()
            return "unknown"
        except Exception as e:
            self.buildroot.root_log.debug("Failed to detect chroot distribution: %s", e)
            return "unknown"

    def _rpm_db_executor(self, cmd):
        """Run an rpm query against the chroot, trying alternate --dbpath values."""
        attempts = [list(cmd)]
        if "--root" in cmd and "--dbpath" not in cmd:
            for dbpath in ("/var/lib/rpm", "/usr/lib/sysimage/rpm"):
                alt = list(cmd)
                root_idx = alt.index("--root")
                alt[root_idx + 2:root_idx + 2] = ["--dbpath", dbpath]
                attempts.append(alt)

        last_error = None
        last_output = ""
        for attempt in attempts:
            try:
                output, rc = self._run_out_chroot(attempt)
                text = (output or "").strip()
                # Host rpm often can't open the default sysimage path; keep
                # trying alternate --dbpath values until we get a real result.
                if rc == 0 and text:
                    return output
                if text and "cannot open Packages database" not in text.lower():
                    # e.g. "package X is not installed" with wrong db — continue
                    if rc != 0 and "is not installed" in text.lower():
                        last_output = output
                        continue
                    if rc == 0:
                        return output
                    last_output = output
                elif text:
                    last_output = output
            except Exception as exc:  # pylint: disable=broad-exception-caught
                last_error = exc
                continue
        if last_error and not last_output:
            raise last_error
        return last_output or ""

    def _query_installed_signature_map(self, chrootpath):
        """Map installed package NEVRA -> printable GPG signature string.

        EL9+/Rocky often store signatures in RSAHEADER rather than SIGPGP.
        ``installed_packages.query_packages`` only reads ``%{sigpgp:pgpsig}``,
        which returns ``(none)`` on those distros — so we query both tags here.

        Keys use :func:`nevra_key` so multilib/same-name packages do not clobber
        each other.
        """
        cmd = ["rpm", "-qa"]
        if chrootpath and chrootpath != "/":
            cmd += ["--root", chrootpath]
        # N E V R A \\t sigpgp \\t rsa \\t dsa \\t siggpg
        cmd += [
            "--qf",
            "%{NAME}\t%{EPOCH}\t%{VERSION}\t%{RELEASE}\t%{ARCH}\t"
            "%{SIGPGP:pgpsig}\t%{RSAHEADER:pgpsig}\t"
            "%{DSAHEADER:pgpsig}\t%{SIGGPG:pgpsig}\n",
        ]
        try:
            output = self._rpm_db_executor(cmd)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self.buildroot.root_log.debug(
                "Installed package signature query failed: %s", exc
            )
            return {}

        sig_map = {}
        for line in (output or "").splitlines():
            parts = line.split("\t")
            if len(parts) < 6:
                continue
            name = parts[0].strip()
            if not name or name.startswith("gpg-pubkey"):
                continue
            epoch = parts[1].strip()
            version = parts[2].strip()
            release = parts[3].strip()
            arch = parts[4].strip()
            key = nevra_key(name, version, release=release, arch=arch, epoch=epoch)
            raw = None
            for part in parts[5:]:
                part = (part or "").strip()
                if part and part != "(none)":
                    raw = part
                    break
            if raw:
                sig_map[key] = raw
        return sig_map

    def _signature_info_from_installed(self, raw_sig):
        """Build signature_info from an installed-package pgpsig string.

        Presence of a signature only yields ``present-unverified``.
        Cryptographic ``verified`` requires ``rpm --checksig`` on the package
        artifact (see verify_rpm_signature). Keyring membership is not enough.
        """
        return self.parse_signature_data(raw_sig)

    def get_build_toolchain_packages(self, generate_cpe=False):
        """Return packages installed in the build chroot (the toolchain).

        Uses mockbuild.installed_packages.query_packages (same path as
        package_state / buildroot_lock) via doOutChroot, with a --dbpath
        fallback for older chroots whose RPM DB lives under /var/lib/rpm.

        Signature data is enriched via RSAHEADER/SIGPGP because modern
        EL/Rocky packages often have an empty SIGPGP tag.
        """
        from mockbuild.installed_packages import query_packages

        chrootpath = self._chroot_root()
        if not self._usable_buildroot(chrootpath):
            self.buildroot.root_log.warning(
                "Skipping toolchain package query: no usable Mock buildroot "
                "(refusing host '/' to avoid recording host RPMs as toolchain)"
            )
            return []

        fields = [
            "name", "version", "release", "arch", "license", "epoch",
            "sigmd5", "signature", "buildtime", "sourcerpm", "sha256header",
        ]

        try:
            raw_packages = query_packages(fields, chrootpath, self._rpm_db_executor)
        except Exception as exc:
            self.buildroot.root_log.warning(
                "Failed to query build toolchain packages: %s", exc
            )
            return []

        # Best-effort download URLs via repoquery (same helper as buildroot_lock)
        try:
            from mockbuild.installed_packages import query_packages_location
            query_packages_location(raw_packages, chrootpath, self._rpm_db_executor)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self.buildroot.root_log.debug(
                "Toolchain package URL lookup skipped: %s", exc
            )

        # Full signature strings (RSAHEADER fallback). Do not promote to
        # verified based on keyring membership alone — that requires checksig.
        sig_map = self._query_installed_signature_map(chrootpath)

        packages = []
        cpe_vendor_default = self.detect_chroot_distribution() or "unknown"
        signed_count = 0
        for pkg in raw_packages:
            package_name = pkg.get("name") or ""
            if not package_name or package_name.startswith("gpg-pubkey"):
                continue

            version = pkg.get("version") or ""
            release = pkg.get("release") or ""
            package_version = f"{version}-{release}" if release else version
            package_arch = pkg.get("arch") or ""
            package_license = pkg.get("license") or ""
            build_time = pkg.get("buildtime") or ""
            source_rpm = pkg.get("sourcerpm")
            if source_rpm == "(none)":
                source_rpm = None
            package_checksum = pkg.get("sha256header")
            if package_checksum in (None, "(none)"):
                package_checksum = None

            raw_sig = sig_map.get(
                nevra_key(
                    package_name,
                    version,
                    release=release,
                    arch=package_arch,
                    epoch=pkg.get("epoch"),
                )
            )
            if raw_sig:
                digital_signature = self._signature_info_from_installed(raw_sig)
                if digital_signature.get("signature_status") != "unsigned":
                    signed_count += 1
            else:
                # Fallback: truncated 8-char key from query_packages "signature"
                sig_short = pkg.get("signature")
                digital_signature = self._empty_signature_info()
                if sig_short:
                    digital_signature["signature_type"] = "GPG"
                    digital_signature["signature_key"] = sig_short
                    digital_signature["signature_status"] = "present-unverified"
                    digital_signature["signature_valid"] = False
                    digital_signature["raw_signature_data"] = sig_short
                    signed_count += 1

            if build_time and str(build_time).isdigit():
                try:
                    dt = datetime.fromtimestamp(int(build_time), tz=timezone.utc)
                    digital_signature["build_date"] = dt.isoformat()
                except (ValueError, TypeError, OverflowError):
                    pass

            cpe = None
            cpe_confidence = None
            if generate_cpe:
                cpe, cpe_confidence = self.generate_cpe(
                    package_name, package_version, vendor=cpe_vendor_default
                )

            entry = {
                "name": package_name,
                "version": package_version,
                "arch": package_arch,
                "epoch": pkg.get("epoch"),
                "licenseDeclared": package_license,
                "digital_signature": digital_signature,
                "sourcerpm": source_rpm,
                "checksum": package_checksum,
                "url": pkg.get("url"),
            }
            if cpe:
                entry["cpe"] = cpe
                entry["cpe_confidence"] = cpe_confidence
            packages.append(entry)

        self.buildroot.root_log.info(
            "Found %s build toolchain packages (%s with signatures)",
            len(packages), signed_count,
        )
        return packages

    def get_distribution(self):
        """Detects the distribution from the chroot environment (human readable)."""
        if not self._usable_buildroot():
            return "Unknown"
        try:
            os_release = os.path.join(self.buildroot.rootdir, "etc/os-release")
            distro_name = "Unknown"
            version = ""
            if os.path.isfile(os_release):
                with open(os_release, 'r', encoding='utf-8') as f:
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

    def get_distribution_version(self):
        """Return VERSION_ID from the chroot os-release, or empty string."""
        if not self._usable_buildroot():
            return ""
        try:
            os_release = os.path.join(self.buildroot.rootdir, "etc/os-release")
            if os.path.isfile(os_release):
                with open(os_release, 'r', encoding='utf-8') as handle:
                    for line in handle:
                        if line.startswith("VERSION_ID="):
                            return line.strip().split("=", 1)[1].strip('"').strip("'")
        except OSError:
            pass
        return ""

    def load_buildroot_lock(self):
        """Load buildroot_lock.json from the result directory when present."""
        resultdir = getattr(self.buildroot, "resultdir", None)
        if not resultdir:
            return None
        lock_path = os.path.join(resultdir, "buildroot_lock.json")
        if not os.path.isfile(lock_path):
            # Also check parent of resultdir (mock layout: .../el9/result vs .../el9/)
            parent = os.path.dirname(resultdir.rstrip("/"))
            alt = os.path.join(parent, "buildroot_lock.json")
            lock_path = alt if os.path.isfile(alt) else lock_path
        if not os.path.isfile(lock_path):
            return None
        try:
            with open(lock_path, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, ValueError) as exc:
            self.buildroot.root_log.warning(
                "Failed to read buildroot_lock.json: %s", exc
            )
            return None
