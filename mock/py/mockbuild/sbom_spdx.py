# -*- coding: utf-8 -*-
# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# SPDX-License-Identifier: GPL-2.0-or-later
# Written by Scott R. Shinn <scott@atomicorp.com>
# Copyright (C) 2026, Atomicorp, Inc.
"""
SPDX generation functions for the SBOM generator plugin.
"""

import hashlib
import os
import re
import uuid
from datetime import datetime, timezone

from mockbuild.sbom_utils import should_include_rpm_file, resolve_rpm_dependency



# pylint: disable=too-many-instance-attributes
class SpdxGenerator:
    """Helper class for generating SPDX documents."""

    @staticmethod
    def _sha1_hex(data):
        """SHA-1 digest for SPDX identifiers (not a security use).

        SPDX requires SHA-1 for packageVerificationCode. On FIPS Python builds,
        hashlib.sha1() fails unless usedforsecurity=False.
        """
        try:
            return hashlib.sha1(data, usedforsecurity=False).hexdigest()
        except TypeError:
            # Python < 3.9 has no usedforsecurity kwarg
            return hashlib.sha1(data).hexdigest()

    def __init__(self, rpm_helper, buildroot, conf=None):
        self.rpm_helper = rpm_helper
        self.buildroot = buildroot
        self.conf = conf or {}

        # Configuration options for file-level dependencies and filtering
        self.include_file_dependencies = self.conf.get("include_file_dependencies", False)
        self.include_file_components = self.conf.get("include_file_components", True)
        self.include_debug_files = self.conf.get("include_debug_files", False)
        self.include_man_pages = self.conf.get("include_man_pages", True)
        self.include_source_dependencies = self.conf.get(
            "include_source_dependencies", True
        )
        self.include_toolchain_dependencies = self.conf.get(
            "include_toolchain_dependencies", False
        )

    @staticmethod
    def _toolchain_signer_group(sig_info):
        """Return (group_key, group_name, group_comment) for a toolchain package.

        Distinguishes unsigned packages from signed packages whose key id could
        not be parsed.
        """
        sig_info = sig_info or {}
        status = (sig_info.get("signature_status") or "unsigned").lower()
        key_id = sig_info.get("signature_key")
        if status in ("present-unverified", "verified") and not key_id:
            return (
                "unknown-key",
                "Packages with unparsed signature key",
                "Grouping for build toolchain packages whose signature is "
                "present but whose GPG key id could not be parsed.",
            )
        if key_id:
            return (
                key_id,
                f"Packages signed by {key_id}",
                f"Grouping for build toolchain packages signed with GPG key {key_id}.",
            )
        return (
            "unsigned",
            "Unsigned Packages",
            "Grouping for build toolchain packages with no signature present.",
        )

    @staticmethod
    def _document_uuid_seed(epoch, name, version, release, distro_id=None, arch=None):
        """Build a deterministic UUIDv5 seed for SPDX documentNamespace.

        Includes distro and arch so identical N-V-R rebuilds for different
        targets do not share a namespace under the same SOURCE_DATE_EPOCH.
        """
        return (
            f"mock-sbom:{epoch}:{name}-{version}-{release}"
            f":{distro_id or 'unknown'}:{arch or 'unknown'}"
        )

    # pylint: disable=too-many-locals,too-many-branches,too-many-statements,too-many-arguments,too-many-positional-arguments
    def generate_spdx_document(self, name, version, release, build_dir, rpm_files,
                               source_files, build_toolchain_packages, distro_id,
                               spec_metadata=None, hardening_props=None):
        """Generates the full SPDX document using hierarchical grouping and enhanced metadata."""
        doc_spdx_id = "SPDXRef-DOCUMENT"
        # Prefer arch from the first binary build output for namespace identity.
        primary_arch = None
        for rpm_file in rpm_files or []:
            if rpm_file.endswith(".src.rpm"):
                continue
            meta = self.rpm_helper.get_rpm_metadata(
                os.path.join(build_dir, rpm_file)
            ) or {}
            arch = meta.get("arch")
            if arch and arch != "(none)":
                primary_arch = arch
                break

        epoch = os.environ.get("SOURCE_DATE_EPOCH")
        if epoch and str(epoch).isdigit():
            creation_time = datetime.fromtimestamp(
                int(epoch), tz=timezone.utc
            ).strftime("%Y-%m-%dT%H:%M:%SZ")
            doc_uuid = uuid.uuid5(
                uuid.NAMESPACE_URL,
                self._document_uuid_seed(
                    epoch, name, version, release, distro_id, primary_arch
                ),
            )
        else:
            creation_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            doc_uuid = uuid.uuid4()

        # 1. Initialize Document
        document = {
            "spdxVersion": "SPDX-2.3",
            "dataLicense": "CC0-1.0",
            "SPDXID": doc_spdx_id,
            "name": f"SBOM for {name}-{version}-{release}",
            "documentNamespace": (
                f"http://spdx.org/spdxdocs/{name}-{version}-{release}-{doc_uuid}"
            ),
            "creationInfo": {
                "creators": [
                    "Tool: mock-sbom-generator-1.0",
                    "Organization: Atomicorp"
                ],
                "created": creation_time
            },
            "packages": [],
            "files": [],
            "relationships": []
        }

        # 1.5 Add Spec Metadata and Hardening Props as SPDX annotations
        annotations = []
        if spec_metadata:
            build_reqs = spec_metadata.get("build_requires", [])
            if build_reqs:
                annotations.append({
                    "annotationDate": creation_time,
                    "annotationType": "OTHER",
                    "annotator": "Tool: mock-sbom-generator",
                    "comment": f"mock:spec:build_requires={','.join(build_reqs)}",
                })
            reqs = spec_metadata.get("requires", [])
            if reqs:
                annotations.append({
                    "annotationDate": creation_time,
                    "annotationType": "OTHER",
                    "annotator": "Tool: mock-sbom-generator",
                    "comment": f"mock:spec:requires={','.join(reqs)}",
                })

        # Hardening flags / network props as machine-readable annotations
        if hardening_props:
            for prop in hardening_props:
                annotations.append({
                    "annotationDate": creation_time,
                    "annotationType": "OTHER",
                    "annotator": "Tool: mock-sbom-generator",
                    "comment": f"{prop['name']}={prop['value']}",
                })

        if annotations:
            document["annotations"] = annotations
            # Keep a short human-readable summary in comment for older consumers
            document["comment"] = (
                f"{len(annotations)} build metadata annotations; "
                "see annotations[] for structured details."
            )

        # Virtual Grouping Refs
        inputs_ref = "SPDXRef-Build-Inputs"
        toolchain_ref = "SPDXRef-Build-Toolchain"
        outputs_ref = "SPDXRef-RPM-Contents"

        # 2. Add Grouping Packages (Represented as virtual packages)
        document["packages"].extend([
            {
                "name": "Build Inputs",
                "SPDXID": inputs_ref,
                "downloadLocation": "NOASSERTION",
                "filesAnalyzed": False,
                "comment": "Grouping node for source files and patches used in the build."
            },
            {
                "name": "Build Toolchain",
                "SPDXID": toolchain_ref,
                "downloadLocation": "NOASSERTION",
                "filesAnalyzed": False,
                "comment": "Grouping node for packages and tools used to perform the build."
            },
            {
                "name": "RPM Contents",
                "SPDXID": outputs_ref,
                "downloadLocation": "NOASSERTION",
                "filesAnalyzed": False,
                "comment": "Grouping node for RPM packages and their contained files produced by the build."
            }
        ])

        # Core relationships for the grouped architecture
        document["relationships"].extend([
            {"spdxElementId": doc_spdx_id, "relatedSpdxElement": inputs_ref, "relationshipType": "CONTAINS"},
            {"spdxElementId": doc_spdx_id, "relatedSpdxElement": toolchain_ref, "relationshipType": "CONTAINS"},
            {"spdxElementId": doc_spdx_id, "relatedSpdxElement": outputs_ref, "relationshipType": "CONTAINS"}
        ])

        # 3. Process Source Files (Inputs)
        for src_file in source_files:
            spdx_file = self.create_spdx_file(src_file)
            if spdx_file:
                document["files"].append(spdx_file)
                if self.include_source_dependencies:
                    document["relationships"].append({
                        "spdxElementId": inputs_ref,
                        "relatedSpdxElement": spdx_file["SPDXID"],
                        "relationshipType": "CONTAINS"
                    })

        # 4. Process Build Toolchain (Grouped by Signer)
        signer_groups = {}
        for tc_pkg in build_toolchain_packages:
            group_key, group_name, group_comment = self._toolchain_signer_group(
                tc_pkg.get("digital_signature")
            )

            if group_key not in signer_groups:
                safe_key = re.sub(r'[^a-zA-Z0-9.-]', '-', group_key)
                signer_ref = f"SPDXRef-Signer-{safe_key}"
                signer_pkg = {
                    "name": group_name,
                    "SPDXID": signer_ref,
                    "downloadLocation": "NOASSERTION",
                    "filesAnalyzed": False,
                    "comment": group_comment,
                }
                document["packages"].append(signer_pkg)
                document["relationships"].append({
                    "spdxElementId": toolchain_ref,
                    "relatedSpdxElement": signer_ref,
                    "relationshipType": "DEPENDS_ON"
                })
                signer_groups[group_key] = signer_ref

            spdx_pkg = self.create_spdx_package_from_dict(tc_pkg, distro_id)
            if spdx_pkg:
                document["packages"].append(spdx_pkg)
                document["relationships"].append({
                    "spdxElementId": signer_groups[group_key],
                    "relatedSpdxElement": spdx_pkg["SPDXID"],
                    "relationshipType": "DEPENDS_ON"
                })

        # 5. Process Build Artifacts (Outputs)
        all_built_packages = []
        name_map = {}
        provides_map = {}

        # Index toolchain packages for Requires resolution.
        for tc_pkg in build_toolchain_packages:
            spdx_id = None
            # Recompute SPDXID the same way create_spdx_package_from_dict does.
            tc_name = tc_pkg.get("name")
            tc_version = tc_pkg.get("version")
            if not tc_name or not tc_version:
                continue
            purl = self.rpm_helper.generate_purl(
                tc_name, tc_version, distro_id,
                arch=tc_pkg.get("arch"),
                epoch=tc_pkg.get("epoch"),
            )
            spdx_id = self._spdx_id_from_purl(purl)
            name_map[tc_name.lower()] = spdx_id

        installed_provides = self.rpm_helper.get_installed_provides_map(
            package_names=list(name_map.keys()) or None
        )
        for capability, pkg_name in installed_provides.items():
            target = name_map.get(pkg_name)
            if target:
                provides_map.setdefault(capability, target)

        for rpm_file in rpm_files:
            rpm_path = os.path.join(build_dir, rpm_file)
            spdx_pkg = self.create_spdx_package_from_rpm(rpm_path, distro_id)
            if spdx_pkg:
                all_built_packages.append((spdx_pkg, rpm_path))
                document["packages"].append(spdx_pkg)
                document["relationships"].append({
                    "spdxElementId": outputs_ref,
                    "relatedSpdxElement": spdx_pkg["SPDXID"],
                    "relationshipType": "DEPENDS_ON"
                })
                pkg_name = (spdx_pkg.get("name") or "").lower()
                if pkg_name and not rpm_file.endswith(".src.rpm"):
                    name_map[pkg_name] = spdx_pkg["SPDXID"]
                    for capability in self.rpm_helper.get_rpm_provides(rpm_path) or []:
                        provides_map.setdefault(capability.lower(), spdx_pkg["SPDXID"])
                        bare = capability.split("(", 1)[0].strip().lower()
                        if bare:
                            provides_map.setdefault(bare, spdx_pkg["SPDXID"])

                # Add file components if enabled and SPDX-valid (needs SHA1
                # digests for packageVerificationCode when filesAnalyzed).
                if self.include_file_components:
                    file_spdx_objs = self.create_file_components(
                        rpm_path, spdx_pkg["SPDXID"]
                    )
                    verification = (
                        self._package_verification_code(file_spdx_objs)
                        if file_spdx_objs else None
                    )
                    if verification:
                        for file_obj in file_spdx_objs:
                            document["files"].append(file_obj)
                            # CONTAINS is the package→file containment edge.
                            document["relationships"].append({
                                "spdxElementId": spdx_pkg["SPDXID"],
                                "relatedSpdxElement": file_obj["SPDXID"],
                                "relationshipType": "CONTAINS"
                            })
                            # Optional inverse edge (mirrors CycloneDX file deps).
                            if self.include_file_dependencies:
                                document["relationships"].append({
                                    "spdxElementId": file_obj["SPDXID"],
                                    "relatedSpdxElement": spdx_pkg["SPDXID"],
                                    "relationshipType": "DEPENDENCY_OF"
                                })
                        spdx_pkg["packageVerificationCode"] = {
                            "packageVerificationCodeValue": verification,
                        }
                    else:
                        # SPDX 2.3 §7.8.1: filesAnalyzed false means no file
                        # info. Modern RPM digests are SHA256, so we cannot
                        # form a SHA1 verification code — omit files/CONTAINS.
                        spdx_pkg["filesAnalyzed"] = False

        # Runtime Requires → DEPENDS_ON for each built binary RPM
        for spdx_pkg, rpm_path in all_built_packages:
            if (rpm_path or "").endswith(".src.rpm"):
                continue
            for raw_dep in self.rpm_helper.get_rpm_dependencies(rpm_path) or []:
                target = resolve_rpm_dependency(
                    raw_dep, name_map, provides_map=provides_map
                )
                if target and target != spdx_pkg["SPDXID"]:
                    document["relationships"].append({
                        "spdxElementId": spdx_pkg["SPDXID"],
                        "relatedSpdxElement": target,
                        "relationshipType": "DEPENDS_ON",
                    })

        # Optional: built packages DEPENDS_ON the build toolchain grouping
        if self.include_toolchain_dependencies and all_built_packages:
            for spdx_pkg, _ in all_built_packages:
                document["relationships"].append({
                    "spdxElementId": spdx_pkg["SPDXID"],
                    "relatedSpdxElement": toolchain_ref,
                    "relationshipType": "DEPENDS_ON"
                })

        # 6. Select Primary Package for DESCRIBES relationship
        if all_built_packages:
            # Logic: Avoid debuginfo, prefer exact name match
            primary_pkg_ref = self._select_primary_package(all_built_packages, name)
            document["relationships"].append({
                "spdxElementId": doc_spdx_id,
                "relatedSpdxElement": primary_pkg_ref,
                "relationshipType": "DESCRIBES"
            })

        return document

    def _select_primary_package(self, pkg_tuples, subject_name):
        """Selects the most suitable primary package from the list of built RPMs."""
        # tuples are (spdx_pkg, rpm_path)
        candidates = [t for t in pkg_tuples if "debuginfo" not in t[0]["name"].lower()]
        if not candidates:
            candidates = pkg_tuples

        # Prefer exact name match
        for pkg, _ in candidates:
            if pkg["name"].lower() == subject_name.lower():
                return pkg["SPDXID"]

        # Fallback to the first non-debuginfo candidate
        return candidates[0][0]["SPDXID"]

    @staticmethod
    def _package_verification_code(file_objs):
        """Compute SPDX packageVerificationCode from analyzed file checksums.

        SPDX sorts the per-file SHA1 digests ascending and SHA1-hashes the
        concatenation. Every emitted file must contribute a SHA1 digest —
        partial coverage would under-hash the analyzed set. Non-SHA1 digests
        are never substituted.

        Returns None when any file lacks SHA1; callers must then omit file
        entries/CONTAINS relationships and set ``filesAnalyzed`` to false so
        the document stays SPDX 2.3 valid.
        """
        if not file_objs:
            return None
        digests = []
        for file_obj in file_objs:
            sha1_value = None
            for checksum in file_obj.get("checksums") or []:
                value = (checksum.get("checksumValue") or "").strip().lower()
                if not value:
                    continue
                alg = (checksum.get("algorithm") or "").upper().replace("-", "")
                if alg == "SHA1":
                    sha1_value = value
                    break
            if not sha1_value:
                return None
            digests.append(sha1_value)
        digests.sort()
        return SpdxGenerator._sha1_hex("".join(digests).encode("utf-8"))

    @staticmethod
    def _spdx_id_from_purl(purl):
        """Derive a unique SPDXRef from a complete package PURL.

        Preserves the existing sanitization (``[^a-zA-Z0-9.-]`` → ``-``) while
        appending a short digest of the original PURL so distinct unsanitized
        values cannot collide after sanitization.
        """
        body = purl[4:] if purl.startswith("pkg:") else purl
        safe = re.sub(r'[^a-zA-Z0-9.-]', '-', body)
        safe = re.sub(r'-{2,}', '-', safe).strip('-')
        digest = SpdxGenerator._sha1_hex(purl.encode("utf-8"))[:12]
        return f"SPDXRef-Package-{safe}-{digest}"

    # pylint: disable=too-many-locals,too-many-branches,too-many-statements
    def create_spdx_package_from_rpm(self, rpm_path, distro_obj):
        """Creates an SPDX Package from an RPM file, including all header metadata."""
        pkg_data = self.rpm_helper.get_rpm_metadata(rpm_path)
        if not pkg_data:
            self.buildroot.root_log.debug(
                "[SBOM] FAILED to get metadata for %s, skipping SPDX package", rpm_path
            )
            return None

        name = pkg_data.get("name")
        version = pkg_data.get("version")
        release = pkg_data.get("release")
        full_version = f"{version}-{release}" if release else version

        purl = self.rpm_helper.generate_purl(
            name, full_version, distro_obj, pkg_data.get("arch"),
            epoch=pkg_data.get("epoch"),
        )
        spdx_id = self._spdx_id_from_purl(purl)

        # SPDX Package Structure
        package = {
            "name": name,
            "SPDXID": spdx_id,
            "versionInfo": full_version,
            "downloadLocation": "NOASSERTION",
            "filesAnalyzed": self.include_file_components,
            "supplier": "NOASSERTION",
            "homepage": "NOASSERTION"
        }

        # Map RPM Header Fields to SPDX pkg fields or comments
        lic = pkg_data.get("license")
        if lic and lic != "(none)":
            package["licenseDeclared"] = lic
        else:
            package["licenseDeclared"] = "NOASSERTION"
        package["licenseConcluded"] = "NOASSERTION"
        package["copyrightText"] = "NOASSERTION"

        url = pkg_data.get("url")
        if url and url != "(none)":
            package["homepage"] = url

        packager = pkg_data.get("packager")
        if packager and packager != "(none)":
            package["supplier"] = f"Person: {packager}"

        # Store additional RPM metadata in a comment block
        metadata_fields = []
        for key, label in [("vendor", "Vendor"), ("buildhost", "Build Host"),
                          ("group", "Group"), ("epoch", "Epoch"),
                          ("distribution", "Distribution"), ("arch", "Architecture")]:
            val = pkg_data.get(key)
            if val and val != "(none)":
                metadata_fields.append(f"{label}: {val}")

        buildtime = pkg_data.get("buildtime")
        if buildtime:
            try:
                dt = datetime.fromtimestamp(int(buildtime), timezone.utc)
                metadata_fields.append(f"Build Time: {dt.isoformat()}")
            except (ValueError, TypeError):
                pass

        # External References (CPE and PURL)
        external_refs = []
        if self.conf.get("generate_cpe", False):
            vendor = pkg_data.get("vendor")
            cpe, confidence = self.rpm_helper.generate_cpe(name, version, vendor=vendor)
            if cpe:
                external_refs.append({
                    "referenceCategory": "SECURITY",
                    "referenceType": "cpe23Type",
                    "referenceLocator": cpe,
                    "comment": f"confidence={confidence}",
                })

        if purl:
            external_refs.append({
                "referenceCategory": "PACKAGE-MANAGER",
                "referenceType": "purl",
                "referenceLocator": purl
            })

        if external_refs:
            package["externalRefs"] = external_refs

        # Evidence-backed signature status (same keys as CycloneDX properties)
        sig_info = self.rpm_helper.verify_rpm_signature(rpm_path)
        metadata_fields.extend(self._signature_metadata_fields(sig_info))

        if metadata_fields:
            package["comment"] = " | ".join(metadata_fields)

        # Full RPM file digest for package integrity (not RPMTAG_SHA256HEADER).
        host = self.rpm_helper.host_path(rpm_path)
        rpm_hash = None
        if os.path.isfile(host):
            rpm_hash = self.rpm_helper.hash_file(host)
        header_sha = pkg_data.get("sha256")
        if header_sha and header_sha not in (None, "", "(none)"):
            # Preserve header digest separately from the artifact checksum.
            comment = package.get("comment") or ""
            header_note = f"mock:rpm:sha256header={header_sha}"
            package["comment"] = (
                f"{comment} | {header_note}" if comment else header_note
            )
        if rpm_hash:
            package["checksums"] = [{"algorithm": "SHA256", "checksumValue": rpm_hash}]

        return package

    @staticmethod
    def _signature_metadata_fields(sig_info):
        """Format signature evidence using CycloneDX-aligned property names."""
        sig_info = sig_info or {}
        fields = [
            f"mock:signature:type={sig_info.get('signature_type', 'unsigned')}",
            f"mock:signature:status={sig_info.get('signature_status', 'unsigned')}",
            f"mock:signature:valid="
            f"{str(bool(sig_info.get('signature_valid'))).lower()}",
        ]
        algorithm = sig_info.get("signature_algorithm")
        if algorithm:
            fields.append(f"mock:signature:algorithm={algorithm}")
        key_id = sig_info.get("signature_key")
        if key_id:
            fields.append(f"mock:signature:key={key_id}")
        sig_date = sig_info.get("signature_date")
        if sig_date:
            fields.append(f"mock:signature:date={sig_date}")
        return fields

    def create_spdx_package_from_dict(self, pkg_data, distro_obj=None):
        """Creates an SPDX Package from a dictionary (e.g. toolchain)."""
        name = pkg_data.get("name")
        version = pkg_data.get("version")
        if not name or not version:
            self.buildroot.root_log.debug(
                "[SBOM] Skipping toolchain package due to missing name/version"
            )
            return None

        purl = self.rpm_helper.generate_purl(
            name, version, distro_obj,
            arch=pkg_data.get("arch"),
            epoch=pkg_data.get("epoch"),
        )
        spdx_id = self._spdx_id_from_purl(purl)

        package = {
            "name": name,
            "SPDXID": spdx_id,
            "versionInfo": version,
            "downloadLocation": "NOASSERTION",
            "filesAnalyzed": False,
            "supplier": "NOASSERTION"
        }

        lic = pkg_data.get("licenseDeclared")
        if lic and lic != "(none)":
            package["licenseDeclared"] = lic
        else:
            package["licenseDeclared"] = "NOASSERTION"
        package["licenseConcluded"] = "NOASSERTION"

        external_refs = []
        if self.conf.get("generate_cpe", False):
            cpe = pkg_data.get("cpe")
            confidence = pkg_data.get("cpe_confidence") or "heuristic"
            if not cpe:
                cpe, confidence = self.rpm_helper.generate_cpe(
                    name, version, vendor=pkg_data.get("vendor")
                )
            if cpe:
                external_refs.append({
                    "referenceCategory": "SECURITY",
                    "referenceType": "cpe23Type",
                    "referenceLocator": cpe,
                    "comment": f"confidence={confidence}",
                })
        if purl:
            external_refs.append({
                "referenceCategory": "PACKAGE-MANAGER",
                "referenceType": "purl",
                "referenceLocator": purl,
            })
        if external_refs:
            package["externalRefs"] = external_refs

        # Toolchain packages carry signature evidence from rpmdb collection.
        sig_fields = self._signature_metadata_fields(
            pkg_data.get("digital_signature") or {}
        )
        if sig_fields:
            package["comment"] = " | ".join(sig_fields)

        return package

    def create_spdx_file(self, file_data, parent_pkg_id=None):
        """Creates an SPDX File from file metadata."""
        filename = file_data.get("filename")
        if not filename:
            return None

        safe_name = re.sub(r'[^a-zA-Z0-9.-]', '-', filename)
        name_digest = self._sha1_hex(filename.encode("utf-8"))[:12]
        # Use a more unique ID if parent is provided
        if parent_pkg_id:
            # Full parent SPDXID hash — last '-' segment is no longer unique with
            # purl-derived package IDs (often ends in arch digits).
            parent_suffix = self._sha1_hex(
                parent_pkg_id.encode("utf-8")
            )[:12]
            spdx_id = f"SPDXRef-File-{safe_name}-{name_digest}-{parent_suffix}"
        else:
            spdx_id = f"SPDXRef-File-{safe_name}-{name_digest}"

        file_obj = {
            "fileName": f"./{filename}",
            "SPDXID": spdx_id,
            "licenseConcluded": "NOASSERTION",
            "copyrightText": "NOASSERTION"
        }

        # Prefer explicit algorithm from RPM file-info; never infer from digest length.
        algo = (file_data.get("digest_algorithm") or "").upper().replace("-", "")
        digest = None
        if algo == "SHA1":
            digest = file_data.get("sha1") or file_data.get("hash")
        elif algo == "SHA256":
            digest = file_data.get("sha256") or file_data.get("hash")
        elif algo == "MD5":
            digest = file_data.get("md5") or file_data.get("hash")
        elif algo in ("SHA384", "SHA512", "SHA224"):
            digest = file_data.get("hash")
        # Minted SHA-1 for verification-code coverage takes precedence.
        if file_data.get("sha1"):
            algo = "SHA1"
            digest = file_data["sha1"]
        if digest and algo in ("SHA1", "SHA256", "MD5", "SHA384", "SHA512", "SHA224"):
            file_obj["checksums"] = [{
                "algorithm": algo,
                "checksumValue": str(digest).strip().lower(),
            }]
        elif not digest:
            # No usable digest — omit checksums (caller may drop from analyzed set).
            pass
        else:
            # Unknown/unsupported algorithm: omit rather than mislabel.
            return None

        # Store GPG flag using CycloneDX-aligned property names when structured.
        sig = file_data.get("digital_signature")
        if isinstance(sig, dict):
            fields = self._signature_metadata_fields(sig)
            if fields:
                file_obj["comment"] = " | ".join(fields)
        elif sig:
            file_obj["comment"] = f"mock:signature:status={sig}"

        return file_obj

    def create_file_components(self, rpm_path, parent_spdx_id):
        """Extracts file list from an RPM and creates SPDX File objects.

        When RPM payload digests are not SHA-1, optionally mint SHA-1 from
        readable chroot paths so packageVerificationCode can be formed. Never
        relabel SHA-256 digests as SHA-1. If too few files are readable, the
        caller falls back to ``filesAnalyzed=false``.
        """
        file_info = self.rpm_helper.get_rpm_file_info(rpm_path) or {}
        spdx_files = []

        for filename in sorted(file_info.keys()):
            f_data = dict(file_info[filename])
            f_data["filename"] = filename

            # Shared filter with CycloneDX
            if not should_include_rpm_file(
                filename,
                include_debug_files=self.include_debug_files,
                include_man_pages=self.include_man_pages,
            ):
                continue

            # Mint SHA-1 from chroot contents when payload digests are not SHA-1.
            if not f_data.get("sha1"):
                host_candidate = self.rpm_helper.host_path(filename)
                if (
                    host_candidate
                    and os.path.isfile(host_candidate)
                    and self.rpm_helper.path_stays_in_chroot(host_candidate)
                ):
                    minted = self.rpm_helper.hash_file(
                        host_candidate, require_in_chroot=True, algorithm="sha1"
                    )
                    if minted:
                        f_data["sha1"] = minted
                        f_data["digest_algorithm"] = "SHA1"

            f_obj = self.create_spdx_file(f_data, parent_pkg_id=parent_spdx_id)
            if f_obj:
                spdx_files.append(f_obj)

        return spdx_files
