# -*- coding: utf-8 -*-
# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# SPDX-License-Identifier: GPL-2.0-or-later
# Written by Scott R. Shinn <scott@atomicorp.com>
# Copyright (C) 2026, Atomicorp, Inc.
"""Core SBOM generation logic shared by the mock plugin and mock-sbom-generator."""

from mockbuild.sbom_utils import RpmQueryHelper, nevra_key
from mockbuild.sbom_spdx import SpdxGenerator
from mockbuild.sbom_cyclonedx import CycloneDxGenerator
import os
import json
import subprocess
import socket
import tempfile
from datetime import datetime, timezone


class SBOMGenerator:
    """Generates SBOM for the built packages."""
    # pylint: disable=too-few-public-methods,too-many-instance-attributes
    def __init__(self, conf, buildroot, prebuild_source_files=None, prebuild_spec_metadata=None,
                 prebuild_capture_errors=None, prebuild_input_srpm=None,
                 injected_host_properties=None, injected_hardening_properties=None):
        """Create an SBOM generator.

        Args:
            conf: Plugin/CLI option dictionary.
            buildroot: Mock Buildroot or a StandaloneContext duck-type.
            prebuild_source_files: Optional list captured before the build.
            prebuild_spec_metadata: Optional spec metadata captured before the build.
            prebuild_capture_errors: Optional list of prebuild capture failure messages.
            prebuild_input_srpm: Optional signed input SRPM metadata from originals/.
            injected_host_properties: Optional host forensics captured on the Mock
                host (hostname, SELinux, host distro, kernel) and passed in so
                bootstrap execution does not re-query the wrong process context.
            injected_hardening_properties: Optional hardening macro properties
                captured on the Mock host via ``rpm --root`` (not bootstrap rpm).
        """
        self.buildroot = buildroot
        self.conf = conf or {}
        self.rpm_helper = RpmQueryHelper(self.buildroot)
        self.spdx_gen = SpdxGenerator(self.rpm_helper, self.buildroot, conf=self.conf)
        self.cdx_gen = CycloneDxGenerator(self.rpm_helper, self.buildroot, conf=self.conf)
        self.state = getattr(buildroot, "state", None)
        self.rootdir = getattr(buildroot, "rootdir", None)
        self.builddir = getattr(buildroot, "builddir", None)
        self.sbom_enabled = self.conf.get('generate_sbom', True)
        self.sbom_type = self.conf.get('type', 'cyclonedx')
        self.sbom_done = False
        self.prebuild_input_srpm = prebuild_input_srpm

        self.prebuild_source_files = prebuild_source_files or []
        self.prebuild_spec_metadata = prebuild_spec_metadata or {}
        self.prebuild_capture_errors = list(prebuild_capture_errors or [])
        self.injected_host_properties = list(injected_host_properties or [])
        self.injected_hardening_properties = list(injected_hardening_properties or [])
        # Per-collector status for evidence-backed completeness
        self.collection_status = {}
        self.collection_errors = []
        # Seed collector failure so completeness cannot stay "complete"
        # when prebuild capture already failed.
        if self.prebuild_capture_errors:
            self._record_collector(
                "prebuild",
                False,
                "; ".join(
                    f"prebuild: {err}" for err in self.prebuild_capture_errors
                ),
            )

    def _record_collector(self, name, success, error=None):
        """Track success/failure of an SBOM data collector."""
        self.collection_status[name] = bool(success)
        if not success:
            msg = error or f"{name} failed"
            self.collection_errors.append(msg)
            self.buildroot.root_log.warning("[SBOM] collector %s: %s", name, msg)

    def _compute_completeness(self):
        """Return complete|partial|minimal based on collector results."""
        if not self.collection_status:
            return "minimal"
        total = len(self.collection_status)
        ok = sum(1 for v in self.collection_status.values() if v)
        if ok == total:
            return "complete"
        if ok == 0:
            return "minimal"
        return "partial"

    def _sbom_timestamp(self):
        """Return ISO timestamp, honoring SOURCE_DATE_EPOCH when set."""
        epoch = os.environ.get("SOURCE_DATE_EPOCH")
        if epoch and str(epoch).isdigit():
            return datetime.fromtimestamp(int(epoch), timezone.utc).isoformat()
        return datetime.now(timezone.utc).isoformat()

    def _host_forensic_properties(self):
        """Capture host-level forensic datapoints."""
        props = []
        try:
            with open("/proc/version", "r", encoding="utf-8") as handle:
                props.append({
                    "name": "mock:host:kernel",
                    "value": handle.read().strip()[:200],
                })
        except OSError:
            pass

        try:
            result = subprocess.run(
                ["getenforce"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                check=False, text=True, env={**os.environ, "LC_ALL": "C"},
            )
            if result.returncode == 0 and result.stdout.strip():
                props.append({
                    "name": "mock:host:selinux",
                    "value": result.stdout.strip().lower(),
                })
        except OSError:
            pass

        try:
            import distro as distro_mod
            host_id = distro_mod.id() or "unknown"
            host_ver = distro_mod.version() or ""
            props.append({
                "name": "mock:host:distribution",
                "value": f"{host_id} {host_ver}".strip(),
            })
        except Exception:  # pylint: disable=broad-exception-caught
            pass

        return props

    def _effective_host_properties(self):
        """Return host forensic properties, preferring host-injected values."""
        if self.injected_host_properties:
            return list(self.injected_host_properties)
        return self._host_forensic_properties()

    def _effective_hardening_properties(self):
        """Return hardening properties, preferring host-injected values."""
        if self.injected_hardening_properties:
            # Macro evidence (not FIPS alone) marks the hardening collector OK.
            macro_prop_names = {
                "build:hardening:optflags",
                "build:hardening:hardening_cflags",
                "build:hardening:global_cflags",
                "build:hardening:global_ldflags",
                "build:hardening:build_ldflags",
            }
            if any(
                p.get("name") in macro_prop_names
                for p in self.injected_hardening_properties
            ):
                self._record_collector("hardening_macros", True)
            else:
                self._record_collector(
                    "hardening_macros", False, "no hardening macros collected"
                )
            return list(self.injected_hardening_properties)
        return self._collect_build_hardening_properties()

    def collect_host_provenance(self):
        """Capture host forensics and hardening macros on the Mock host.

        Intended for the plugin process (not bootstrap). Hardening macros are
        evaluated with the host ``rpm --root <target>`` so results are not
        filtered through bootstrap's RPM personality.

        Returns:
            tuple: (host_metadata_properties, hardening_properties) lists of
            ``{"name": ..., "value": ...}`` dicts suitable for prebuild JSON.
        """
        host_props = [
            {"name": "mock:build:host", "value": socket.gethostname()},
        ]
        host_props.extend(self._host_forensic_properties())
        hardening_props = self._collect_build_hardening_properties(via_host=True)
        return host_props, hardening_props

    def _create_metadata(self):
        """Creates CycloneDX metadata object with Mock-specific build information."""
        metadata = {
            "timestamp": self._sbom_timestamp(),
            "tools": [
                {
                    "vendor": "Mock",
                    "name": "mock-sbom-generator",
                    "version": self.buildroot.config.get('version', 'unknown')
                }
            ],
            "lifecycles": [
                {
                    "phase": "build"
                }
            ],
            "licenses": [
                {
                    "license": {
                        "id": "CC0-1.0"
                    }
                }
            ],
            "properties": []
        }

        properties = metadata["properties"]

        # Evidence-backed completeness (computed after collectors run; placeholder updated later)
        properties.append({
            "name": "sbom:completeness",
            "value": self._compute_completeness(),
        })
        if self.collection_errors:
            properties.append({
                "name": "mock:sbom:collection_errors",
                "value": "; ".join(self.collection_errors),
            })

        # Host identity/forensics: prefer values captured on the Mock host
        # (injected via prebuild JSON) so bootstrap execution does not record
        # nspawn hostname / missing SELinux / wrong distro.
        host_props = self._effective_host_properties()
        hostname_injected = any(
            p.get("name") == "mock:build:host" for p in host_props
        )
        if not hostname_injected:
            properties.append({
                "name": "mock:build:host",
                "value": socket.gethostname()
            })
        properties.extend(host_props)

        distro_name = self.rpm_helper.get_distribution()
        if distro_name:
            properties.append({
                "name": "mock:build:distribution",
                "value": distro_name
            })

        if hasattr(self.buildroot, 'rootdir') and self.buildroot.rootdir:
            properties.append({
                "name": "mock:build:chroot",
                "value": self.buildroot.rootdir
            })

        if hasattr(self.buildroot, 'config') and self.buildroot.config:
            config = self.buildroot.config
            config_name = config.get('config_path', 'unknown')
            properties.append({
                "name": "mock:build:config",
                "value": config_name
            })
            mock_ver = config.get('version')
            if mock_ver:
                properties.append({
                    "name": "mock:build:mock_version",
                    "value": str(mock_ver),
                })

            online = config.get('online', True)
            properties.append({
                "name": "mock:build:network:online",
                "value": str(online).lower()
            })

            rpm_net = config.get('rpmbuild_networking', False)
            properties.append({
                "name": "mock:build:network:rpmbuild",
                "value": str(rpm_net).lower()
            })

            isolation = config.get('isolation')
            if isolation:
                properties.append({
                    "name": "mock:build:isolation",
                    "value": str(isolation)
                })

            use_nspawn = config.get('use_nspawn')
            if use_nspawn is not None:
                properties.append({
                    "name": "mock:build:nspawn",
                    "value": str(use_nspawn).lower()
                })

        # buildroot_lock provenance when available (optional — absence is not an error)
        lock = self.rpm_helper.load_buildroot_lock()
        if lock:
            self._record_collector("buildroot_lock", True)
            lock_ver = lock.get("version")
            if lock_ver:
                properties.append({
                    "name": "mock:buildroot_lock:version",
                    "value": str(lock_ver),
                })
            bootstrap = (lock.get("buildroot") or {}).get("bootstrap") or {}
            if bootstrap.get("image_digest") or bootstrap.get("image_id"):
                properties.append({
                    "name": "mock:buildroot_lock:bootstrap_image",
                    "value": str(
                        bootstrap.get("image_digest")
                        or bootstrap.get("image_id")
                    ),
                })

        hardening_props = self._effective_hardening_properties()
        if hardening_props:
            properties.extend(hardening_props)

        # Refresh completeness now that collectors have run
        for prop in properties:
            if prop.get("name") == "sbom:completeness":
                prop["value"] = self._compute_completeness()
            if prop.get("name") == "mock:sbom:collection_errors":
                prop["value"] = "; ".join(self.collection_errors)

        # Ensure errors property exists if any
        if self.collection_errors and not any(
            p.get("name") == "mock:sbom:collection_errors" for p in properties
        ):
            properties.append({
                "name": "mock:sbom:collection_errors",
                "value": "; ".join(self.collection_errors),
            })

        return metadata

    def _evaluate_rpm_macro_on_host(self, macro):
        """Evaluate an RPM macro with the host ``rpm`` binary and ``--root``.

        Unlike :meth:`_evaluate_rpm_macro`, this never uses ``doOutChroot``, so
        bootstrap's RPM personality cannot under-report target macros. Call
        only from the Mock host process when capturing injectable provenance.
        """
        chrootpath = None
        if hasattr(self.buildroot, "make_chroot_path"):
            chrootpath = self.buildroot.make_chroot_path()
        elif getattr(self.buildroot, "rootdir", None):
            chrootpath = self.buildroot.rootdir

        if not chrootpath or not self.rpm_helper._usable_buildroot(chrootpath):
            self.buildroot.root_log.debug(
                "[SBOM] Skipping host RPM macro %s without a buildroot", macro
            )
            return ""

        cmd = ["rpm", "--root", chrootpath, "--eval", macro]
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                text=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as exc:
            self.buildroot.root_log.debug(
                "Warning: failed to eval macro %s on host: %s", macro, exc
            )
            return ""

    def _evaluate_rpm_macro(self, macro):
        """Evaluate an RPM macro via host/bootstrap rpm with --root (doOutChroot).

        Returns empty string when no usable buildroot is available — never runs
        unrooted ``rpm --eval`` against the host.
        """
        chrootpath = None
        if hasattr(self.buildroot, "make_chroot_path"):
            chrootpath = self.buildroot.make_chroot_path()
        elif getattr(self.buildroot, "rootdir", None):
            chrootpath = self.buildroot.rootdir

        if not chrootpath or not self.rpm_helper._usable_buildroot(chrootpath):
            self.buildroot.root_log.debug(
                "[SBOM] Skipping RPM macro %s without a buildroot", macro
            )
            return ""

        cmd = ["rpm", "--root", chrootpath, "--eval", macro]

        if hasattr(self.buildroot, "doOutChroot"):
            try:
                output, _ = self.buildroot.doOutChroot(
                    cmd,
                    shell=False,
                    returnOutput=True,
                    printOutput=False,
                    returnStderr=False,
                )
                if output:
                    return output.strip()
            except Exception as exc:  # pylint: disable=broad-except
                self.buildroot.root_log.debug(
                    "Warning: failed to eval macro %s via doOutChroot: %s",
                    macro, exc,
                )
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                text=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as exc:
            self.buildroot.root_log.debug(
                "Warning: failed to eval macro %s: %s", macro, exc
            )
            return ""

    def _read_file_from_chroot(self, relative_path):
        """
        Read a file from inside the buildroot.
        Returns the file content as a string or empty string on failure.
        """
        rootdir = getattr(self.buildroot, "rootdir", None)
        if not rootdir:
            return ""
        chroot_path = os.path.join(rootdir, relative_path.lstrip("/"))
        try:
            with open(chroot_path, "r", encoding="utf-8", errors="ignore") as handle:
                return handle.read().strip()
        except (OSError, IOError):
            pass
        return ""

    @staticmethod
    def _flag_enabled(flag_tokens, positives, negatives):
        """Return True if a positive flag token is present and no negative overrides it.

        Negatives are checked first so substring traps like ``-fno-pie`` matching
        ``-pie`` cannot claim a feature is enabled.
        """
        token_set = set(flag_tokens)
        if any(neg in token_set for neg in negatives):
            return False
        return any(pos in token_set for pos in positives)

    def _collect_build_hardening_properties(self, via_host=False):
        """
        Capture key compiler/linker macro settings that influence hardening
        (FORTIFY, PIE, RELRO, LTO, etc.) and expose them as SBOM properties.

        Feature/FIPS true/false bits are only emitted when at least one
        corresponding evidence source was successfully read. Missing evidence
        is omitted (unknown), not reported as false.

        Args:
            via_host (bool): When True, evaluate macros with the host ``rpm``
                binary only (skip ``doOutChroot``). Use for host-side capture
                before injecting into bootstrap SBOM generation.
        """
        macro_queries = {
            "build:hardening:optflags": "%{?optflags}",
            "build:hardening:hardening_cflags": "%{?_hardening_cflags}",
            "build:hardening:global_cflags": "%{?__global_cflags}",
            "build:hardening:global_ldflags": "%{?__global_ldflags}",
            "build:hardening:build_ldflags": "%{?build_ldflags}",
        }

        eval_macro = (
            self._evaluate_rpm_macro_on_host if via_host else self._evaluate_rpm_macro
        )

        properties = []
        macro_values = {}
        macro_evidence = False
        for prop_name, macro in macro_queries.items():
            value = eval_macro(macro)
            macro_values[prop_name] = value
            if value:
                macro_evidence = True
                properties.append({
                    "name": prop_name,
                    "value": value
                })

        if macro_evidence:
            cflags_combined = " ".join(
                filter(
                    None,
                    [
                        macro_values.get("build:hardening:optflags"),
                        macro_values.get("build:hardening:hardening_cflags"),
                        macro_values.get("build:hardening:global_cflags"),
                    ],
                )
            ).lower()
            ldflags_combined = " ".join(
                filter(
                    None,
                    [
                        macro_values.get("build:hardening:global_ldflags"),
                        macro_values.get("build:hardening:build_ldflags"),
                    ],
                )
            ).lower()
            flag_union = f"{cflags_combined} {ldflags_combined}"
            flag_tokens = flag_union.split()

            feature_map = {
                "build:hardening:fortify_enabled": any(
                    token in flag_union
                    for token in ["-d_fortify_source", "_fortify_source="]
                ),
                # Tokenize and check negatives first so "-fno-pie" is not
                # mistaken for "-pie" via substring matching.
                "build:hardening:pie_enabled": self._flag_enabled(
                    flag_tokens,
                    positives=("-fpie", "-pie"),
                    negatives=("-fno-pie", "-nopie", "-no-pie"),
                ),
                "build:hardening:relro_enabled": any(
                    token in flag_union
                    for token in ["-z relro", "-z now", "-wl,-z,relro", "-wl,-z,now"]
                ),
                "build:hardening:lto_enabled": any(
                    t == "-flto" or t.startswith("-flto=") for t in flag_tokens
                ),
            }
            for name, enabled in feature_map.items():
                properties.append({
                    "name": name,
                    "value": "true" if enabled else "false"
                })

        fips_value = self._read_file_from_chroot("/proc/sys/crypto/fips_enabled")
        # Only report chroot evidence. Host /proc is not buildroot hardening.
        if fips_value != "":
            properties.append({
                "name": "build:hardening:fips_enabled",
                "value": "true" if fips_value.strip() == "1" else "false",
            })

        # Collector status is based on macro evidence only (not FIPS/network).
        if macro_evidence:
            self._record_collector("hardening_macros", True)
        else:
            self._record_collector(
                "hardening_macros", False, "no hardening macros collected"
            )

        return properties

    def _find_build_artifacts(self, build_dir):
        """Locates RPMs, source RPMs, and spec files in the build directory."""
        rpm_files = []
        src_rpm_files = []
        spec_file = None

        # Use os.scandir for better performance
        try:
            with os.scandir(build_dir) as entries:
                for entry in entries:
                    if not entry.is_file():
                        continue
                    if entry.name.endswith('.src.rpm'):
                        src_rpm_files.append(entry.name)
                    elif entry.name.endswith('.rpm'):
                        rpm_files.append(entry.name)
        except OSError as e:
            self.buildroot.root_log.debug("Failed to scan build directory %s: %s", build_dir, e)

        # Look for spec file in the chroot build directory (skip when no root)
        build_build_dir = self._chroot_build_dir()
        if build_build_dir:
            if os.path.exists(build_build_dir):
                try:
                    for root, _dirs, files in os.walk(build_build_dir):
                        for file in files:
                            if file.endswith('.spec'):
                                spec_file = os.path.join(root, file)
                                break
                        if spec_file:
                            break
                except OSError as e:
                    self.buildroot.root_log.debug("Failed to scan chroot build dir %s: %s", build_build_dir, e)

        return rpm_files, src_rpm_files, spec_file

    def _chroot_build_dir(self):
        """Host path to the chroot build dir, honoring ``chroothome``.

        Uses ``buildroot.builddir`` (chroot-relative, derived from
        ``config_opts['chroothome']``) via ``make_chroot_path`` when available,
        falling back to the default ``builddir/build`` layout. Returns None
        when no chroot root is configured.
        """
        rootdir = getattr(self.buildroot, "rootdir", None)
        if not rootdir:
            return None
        builddir = self.builddir or "/builddir/build"
        make_path = getattr(self.buildroot, "make_chroot_path", None)
        if callable(make_path):
            path = make_path(builddir)
            if path:
                return path
        return os.path.join(rootdir, builddir.lstrip("/"))

    def _find_originals_input_srpm(self):
        """Locate and fingerprint the signed input SRPM under originals/.

        Returns:
            tuple: ``(entry_or_None, status)`` where status is one of
            ``found``, ``missing``, or ``error``.
        """
        build_dir = self._chroot_build_dir()
        if not build_dir:
            return None, "missing"
        originals_dir = os.path.join(build_dir, "originals")
        try:
            entry = self.rpm_helper.capture_originals_input_srpm(originals_dir)
        except OSError as exc:
            self.buildroot.root_log.debug(
                "[SBOM] Could not read originals input SRPM: %s", exc
            )
            return None, "error"
        if entry:
            return entry, "found"
        return None, "missing"

    @staticmethod
    def _downgrade_unverified_snapshot(srpm_entry):
        """Copy a prebuild snapshot and strip unverifiable ``verified`` status.

        Without a live ``rpm --checksig`` pass, a snapshot claiming
        ``verified`` must be downgraded to ``present-unverified``.
        """
        if not srpm_entry:
            return srpm_entry
        entry = dict(srpm_entry)
        sig = entry.get("digital_signature")
        if not isinstance(sig, dict):
            return entry
        sig = dict(sig)
        if sig.get("signature_status") == "verified" or sig.get("signature_valid"):
            sig["signature_status"] = "present-unverified"
            sig["signature_valid"] = False
        entry["digital_signature"] = sig
        return entry

    @staticmethod
    def _nevra_key(entry):
        """Identity key shared by buildroot_lock and toolchain packages.

        Lock entries have separate version/release; toolchain packages already
        store version as ``V-R``.
        """
        return nevra_key(
            entry.get("name"),
            entry.get("version"),
            release=entry.get("release"),
            arch=entry.get("arch"),
            epoch=entry.get("epoch"),
        )

    def _record_input_srpm_entry(self, source_files, srpm_entry):
        """Insert or refresh the chain-of-custody input SRPM in source_files."""
        if not srpm_entry:
            return source_files
        srpm_name = srpm_entry.get("filename")
        existing = next(
            (
                entry for entry in source_files
                if entry.get("role") == "input"
                or (
                    srpm_name
                    and entry.get("filename") == srpm_name
                )
            ),
            None,
        )
        if existing:
            existing["filename"] = srpm_name or existing.get("filename")
            existing["sha256"] = srpm_entry.get("sha256") or existing.get("sha256")
            existing["digital_signature"] = (
                srpm_entry.get("digital_signature")
                or existing.get("digital_signature")
            )
            existing["source_type"] = "source_rpm"
            existing["role"] = "input"
        else:
            source_files.insert(0, dict(srpm_entry))
        return source_files

    def _get_build_subject_metadata(self, spec_file, src_rpm_files, build_dir):
        """Determines the build subject metadata (name, version, release).

        Prebuild metadata is used only when it includes a non-empty package name;
        otherwise we re-parse the spec and/or recover from the SRPM.

        Chain-of-custody for the input SRPM prefers a live ``rpm --checksig`` of
        ``builddir/build/originals/*.src.rpm``. A prebuild JSON snapshot is used
        only when the file is gone, and never keeps a ``verified`` status without
        a checksig pass. The result-dir ``*.src.rpm`` is a rebuilt output and is
        only used as a last fallback.
        """
        build_subject_name = None
        build_subject_version = None
        build_subject_release = None
        source_files = []
        spec_metadata = {}

        prebuild = getattr(self, "prebuild_spec_metadata", None) or {}
        prebuild_usable = bool(prebuild.get("name"))

        if prebuild_usable:
            spec_metadata = dict(prebuild)
            source_files = list(self.prebuild_source_files or [])
            build_subject_name = spec_metadata.get("name")
            build_subject_version = spec_metadata.get("version")
            build_subject_release = spec_metadata.get("release")
        elif spec_file:
            spec_metadata, parsed_sources = self.rpm_helper.parse_spec_file(spec_file)
            if spec_metadata:
                build_subject_name = spec_metadata.get("name") or None
                build_subject_version = spec_metadata.get("version") or None
                build_subject_release = spec_metadata.get("release") or None
            if parsed_sources:
                source_files = list(parsed_sources)
        elif prebuild and not prebuild_usable:
            self.buildroot.root_log.warning(
                "[SBOM] Ignoring empty prebuild spec metadata; will recover from "
                "spec/SRPM"
            )

        # Prefer live originals/ checksig; fall back to prebuild snapshot only
        # when the file is confirmed missing (never on I/O error; never mint
        # verified without checksig).
        input_srpm, input_status = self._find_originals_input_srpm()
        if input_status == "found":
            self._record_collector("input_srpm", True)
        elif input_status == "error":
            self._record_collector(
                "input_srpm", False, "failed reading originals/ input SRPM"
            )
            input_srpm = None
        elif input_status == "missing":
            snapshot = getattr(self, "prebuild_input_srpm", None) or None
            if snapshot:
                input_srpm = self._downgrade_unverified_snapshot(snapshot)
                self._record_collector("input_srpm", True)
            # Confirmed absence without snapshot is not a collector failure
            # (spec-based builds often have no originals/ SRPM).
        if input_srpm:
            source_files = self._record_input_srpm_entry(source_files, input_srpm)

        if src_rpm_files:
            srpm_path = os.path.join(build_dir, src_rpm_files[0])
            srpm_metadata = self.rpm_helper.get_rpm_metadata(srpm_path)
            if srpm_metadata:
                if not build_subject_name:
                    build_subject_name = srpm_metadata.get("name")
                if not build_subject_version:
                    build_subject_version = srpm_metadata.get("version")
                if not build_subject_release:
                    build_subject_release = srpm_metadata.get("release")
                # Merge useful RPM header fields into spec_metadata when missing
                if not spec_metadata.get("name") and build_subject_name:
                    spec_metadata["name"] = build_subject_name
                if not spec_metadata.get("version") and build_subject_version:
                    spec_metadata["version"] = build_subject_version
                if not spec_metadata.get("release") and build_subject_release:
                    spec_metadata["release"] = build_subject_release
                if not spec_metadata.get("license"):
                    lic = srpm_metadata.get("license")
                    if lic and lic != "(none)":
                        spec_metadata["license"] = lic

            srpm_sources = self.rpm_helper.extract_source_files_from_srpm(srpm_path)
            source_files = self.rpm_helper.merge_source_files(source_files, srpm_sources)

            # Only record the result-dir SRPM as the input artifact when we have
            # no signed originals/ input (e.g. standalone rebuild of result only).
            if not input_srpm:
                srpm_name = src_rpm_files[0]
                srpm_sig = self.rpm_helper.verify_rpm_signature(srpm_path)
                srpm_hash = self.rpm_helper.hash_file(srpm_path)
                srpm_entry = {
                    "filename": srpm_name,
                    "sha256": srpm_hash,
                    "digital_signature": srpm_sig,
                    "source_type": "source_rpm",
                    "role": "input",
                }
                source_files = self._record_input_srpm_entry(source_files, srpm_entry)

        return (
            spec_metadata, build_subject_name, build_subject_version,
            build_subject_release, source_files
        )

    def _add_toolchain_components(self, _bom, build_toolchain_packages, distro_id):
        """Adds toolchain components to the BOM and returns their components and bom-refs."""
        toolchain_components = []
        toolchain_bom_refs = []
        for toolchain_pkg in build_toolchain_packages:
            component = self.cdx_gen.create_toolchain_component(toolchain_pkg, distro_id)
            if component:
                bom_ref = component.get("bom-ref")
                if bom_ref:
                    toolchain_bom_refs.append(bom_ref)
                toolchain_components.append(component)
        return toolchain_components, toolchain_bom_refs

    # pylint: disable=too-many-locals
    def generate(self):
        """Generate the SBOM artifact(s) into the result directory.

        Returns:
            bool: True when an SBOM file was successfully written; False on
            skip-with-error or failure. Disabled/already-done returns True.
        """
        self.buildroot.root_log.debug("[SBOM] Starting post-build SBOM generation")
        if self.sbom_done or not self.sbom_enabled:
            return True

        state_text = f"Generating {self.sbom_type.upper()} SBOM for built packages"
        if self.state:
            self.state.start(state_text)

        success = False
        try:
            build_dir = self.buildroot.resultdir
            rpm_files, src_rpm_files, spec_file = self._find_build_artifacts(build_dir)

            if not rpm_files and not src_rpm_files and not spec_file:
                self.buildroot.root_log.warning(
                    "No RPM, source RPM, or spec file found for SBOM generation."
                )
                self._record_collector("artifacts", False, "no build artifacts found")
                return False
            self._record_collector("artifacts", True)

            (
                spec_metadata, build_subject_name, build_subject_version,
                build_subject_release, source_files
            ) = self._get_build_subject_metadata(spec_file, src_rpm_files, build_dir)

            if spec_metadata and spec_metadata.get("name"):
                self._record_collector("spec_metadata", True)
            else:
                self._record_collector("spec_metadata", False, "spec metadata incomplete")

            if source_files:
                self._record_collector("source_files", True)
            else:
                self._record_collector("source_files", False, "no source files collected")

            if not build_subject_name or not build_subject_version or not build_subject_release:
                self.buildroot.root_log.warning(
                    "[SBOM] Cannot generate SBOM - build metadata incomplete"
                )
                return False

            distro_id = self.rpm_helper.detect_chroot_distribution() or "unknown"
            generate_cpe = self.conf.get("generate_cpe", False)
            try:
                build_toolchain_packages = self.rpm_helper.get_build_toolchain_packages(
                    generate_cpe=generate_cpe
                )
                # Merge download URLs from buildroot_lock when present
                lock = self.rpm_helper.load_buildroot_lock()
                if lock:
                    url_map = {}
                    for rpm_entry in (lock.get("buildroot") or {}).get("rpms") or []:
                        if rpm_entry.get("url"):
                            url_map[self._nevra_key(rpm_entry)] = rpm_entry["url"]
                    for pkg in build_toolchain_packages:
                        key = self._nevra_key(pkg)
                        if key in url_map and not pkg.get("url"):
                            pkg["url"] = url_map[key]

                if build_toolchain_packages:
                    self._record_collector("toolchain", True)
                else:
                    self._record_collector("toolchain", False, "toolchain query returned empty")
            except Exception as exc:  # pylint: disable=broad-exception-caught
                build_toolchain_packages = []
                self._record_collector("toolchain", False, str(exc))

            out_file = None
            if self.sbom_type == "spdx":
                sbom_filename = (
                    f"{build_subject_name}-{build_subject_version}-{build_subject_release}.spdx.json"
                )
                out_file = os.path.join(self.buildroot.resultdir, sbom_filename)

                hardening_props = self._effective_hardening_properties()
                # Include network props in SPDX annotations via hardening_props list
                if hasattr(self.buildroot, "config") and self.buildroot.config:
                    cfg = self.buildroot.config
                    hardening_props = list(hardening_props or [])
                    hardening_props.append({
                        "name": "mock:build:network:online",
                        "value": str(cfg.get("online", True)).lower(),
                    })
                    hardening_props.append({
                        "name": "mock:build:network:rpmbuild",
                        "value": str(cfg.get("rpmbuild_networking", False)).lower(),
                    })

                doc = self.spdx_gen.generate_spdx_document(
                    build_subject_name, build_subject_version, build_subject_release,
                    build_dir, rpm_files + src_rpm_files, source_files,
                    build_toolchain_packages, distro_id,
                    spec_metadata=spec_metadata, hardening_props=hardening_props
                )
                # Stamp completeness onto SPDX document annotation
                doc.setdefault("annotations", []).append({
                    "annotationDate": self._sbom_timestamp().replace("+00:00", "Z"),
                    "annotationType": "OTHER",
                    "annotator": "Tool: mock-sbom-generator",
                    "comment": f"sbom:completeness={self._compute_completeness()}",
                })
                if self.collection_errors:
                    doc["annotations"].append({
                        "annotationDate": self._sbom_timestamp().replace("+00:00", "Z"),
                        "annotationType": "OTHER",
                        "annotator": "Tool: mock-sbom-generator",
                        "comment": "mock:sbom:collection_errors=" + "; ".join(
                            self.collection_errors
                        ),
                    })

                self._atomic_write_json(out_file, doc)
                self.buildroot.root_log.info("SPDX SBOM written to: %s", out_file)

            else:
                sbom_filename = (
                    f"{build_subject_name}-{build_subject_version}-{build_subject_release}.sbom"
                )
                out_file = os.path.join(self.buildroot.resultdir, sbom_filename)

                serial_seed = (
                    f"{build_subject_name}-{build_subject_version}-"
                    f"{build_subject_release}"
                )
                bom = self.cdx_gen.create_cyclonedx_document(serial_seed=serial_seed)
                bom["metadata"] = self._create_metadata()

                source_components, source_component_entries = self.cdx_gen.add_source_components(
                    bom, source_files
                )
                toolchain_components, toolchain_bom_refs = self._add_toolchain_components(
                    bom, build_toolchain_packages, distro_id
                )

                (
                    built_package_bom_refs, primary_rpm_metadata, all_built_components
                ) = self.cdx_gen.process_built_packages(
                    bom, rpm_files + src_rpm_files, build_dir, distro_id,
                    source_component_entries,
                    build_subject_name, build_toolchain_packages, toolchain_bom_refs
                )

                self.cdx_gen.finalize_bom_metadata(
                    bom, primary_rpm_metadata, built_package_bom_refs,
                    build_subject_name, build_subject_version,
                    build_subject_release, distro_id,
                    spec_metadata=spec_metadata
                )
                self.cdx_gen.finalize_dependencies(
                    bom, source_component_entries,
                    build_toolchain_packages,
                    built_package_bom_refs, toolchain_bom_refs,
                    source_components=source_components,
                    toolchain_components=toolchain_components,
                    all_built_components=all_built_components
                )

                self._atomic_write_json(out_file, bom)
                self.buildroot.root_log.info("CycloneDX SBOM written to: %s", out_file)

            if out_file and os.path.isfile(out_file):
                self._write_sbom_digest(out_file)
                success = True

            return success

        except Exception as e:  # pylint: disable=broad-exception-caught
            self.buildroot.root_log.warning(
                "[SBOM] FAILED during SBOM generation: %s", e, exc_info=True
            )
            return False
        finally:
            self.sbom_done = True
            if self.state:
                self.state.finish(state_text)

    @staticmethod
    def _atomic_write_text(path, text):
        """Write text to ``path`` via a same-directory temp file + ``os.replace``.

        On failure the destination is left unchanged (if it already existed).
        """
        directory = os.path.dirname(path) or "."
        fd, tmp_path = tempfile.mkstemp(
            prefix=f".{os.path.basename(path)}.",
            suffix=".tmp",
            dir=directory,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    @staticmethod
    def _atomic_write_json(path, payload):
        """Serialize ``payload`` as JSON and publish atomically to ``path``."""
        SBOMGenerator._atomic_write_text(path, json.dumps(payload, indent=2) + "\n")

    def _write_sbom_digest(self, out_file):
        """Write SHA-256 sidecar digest next to the SBOM artifact."""
        digest = self.rpm_helper.hash_file(out_file)
        if not digest:
            return
        digest_path = out_file + ".sha256"
        try:
            self._atomic_write_text(
                digest_path,
                f"{digest}  {os.path.basename(out_file)}\n",
            )
            self.buildroot.root_log.info("SBOM digest written to: %s", digest_path)
        except OSError as exc:
            self.buildroot.root_log.warning("Failed to write SBOM digest: %s", exc)
