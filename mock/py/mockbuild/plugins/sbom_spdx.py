# -*- coding: utf-8 -*-
# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# License: GPL2 or later see COPYING
# Written by Scott R. Shinn <scott@atomicorp.com>
# Copyright (C) 2026, Atomicorp, Inc.
"""
SPDX generation functions for the SBOM generator plugin.
"""

import os
import re
import uuid
from datetime import datetime, timezone



# pylint: disable=too-many-instance-attributes
class SpdxGenerator:
    """Helper class for generating SPDX documents."""

    def __init__(self, rpm_helper, buildroot, conf=None):
        self.rpm_helper = rpm_helper
        self.buildroot = buildroot
        self.conf = conf or {}

        # Configuration options for file-level dependencies and filtering
        self.include_file_dependencies = self.conf.get("include_file_dependencies", False)
        self.include_file_components = self.conf.get("include_file_components", True)
        self.include_debug_files = self.conf.get("include_debug_files", False)
        self.include_man_pages = self.conf.get("include_man_pages", True)
        self.include_toolchain_dependencies = self.conf.get(
            "include_toolchain_dependencies", False
        )

    # pylint: disable=too-many-locals,too-many-branches,too-many-statements,too-many-arguments,too-many-positional-arguments
    def generate_spdx_document(self, name, version, release, build_dir, rpm_files,
                               source_files, build_toolchain_packages, distro_id,
                               spec_metadata=None, hardening_props=None):
        """Generates the full SPDX document using hierarchical grouping and enhanced metadata."""
        doc_spdx_id = "SPDXRef-DOCUMENT"
        creation_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # 1. Initialize Document
        document = {
            "spdxVersion": "SPDX-2.3",
            "dataLicense": "CC0-1.0",
            "SPDXID": doc_spdx_id,
            "name": f"SBOM for {name}-{version}-{release}",
            "documentNamespace": f"http://spdx.org/spdxdocs/{name}-{version}-{release}-{uuid.uuid4()}",
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

        # 1.5 Add Spec Metadata and Hardening Props to Document Comment
        doc_metadata = []
        if spec_metadata:
            build_reqs = spec_metadata.get("build_requires", [])
            if build_reqs:
                doc_metadata.append(f"Build-Requires: {', '.join(build_reqs)}")
            reqs = spec_metadata.get("requires", [])
            if reqs:
                doc_metadata.append(f"Requires: {', '.join(reqs)}")

        # Hardening flags
        if hardening_props:
            for prop in hardening_props:
                doc_metadata.append(f"{prop['name']}: {prop['value']}")

        if doc_metadata:
            document["comment"] = " | ".join(doc_metadata)

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
                document["relationships"].append({
                    "spdxElementId": inputs_ref,
                    "relatedSpdxElement": spdx_file["SPDXID"],
                    "relationshipType": "CONTAINS"
                })

        # 4. Process Build Toolchain (Grouped by Signer)
        signer_groups = {}
        for tc_pkg in build_toolchain_packages:
            sig_info = tc_pkg.get("digital_signature", {})
            key_id = sig_info.get("signature_key", "unsigned")
            
            if key_id not in signer_groups:
                safe_key = re.sub(r'[^a-zA-Z0-9.-]', '-', key_id)
                signer_ref = f"SPDXRef-Signer-{safe_key}"
                signer_pkg = {
                    "name": f"Packages signed by {key_id}" if key_id != "unsigned" else "Unsigned Packages",
                    "SPDXID": signer_ref,
                    "downloadLocation": "NOASSERTION",
                    "filesAnalyzed": False,
                    "comment": f"Grouping for build toolchain packages signed with GPG key {key_id}."
                }
                document["packages"].append(signer_pkg)
                document["relationships"].append({
                    "spdxElementId": toolchain_ref,
                    "relatedSpdxElement": signer_ref,
                    "relationshipType": "DEPENDS_ON"
                })
                signer_groups[key_id] = signer_ref

            spdx_pkg = self.create_spdx_package_from_dict(tc_pkg)
            if spdx_pkg:
                document["packages"].append(spdx_pkg)
                document["relationships"].append({
                    "spdxElementId": signer_groups[key_id],
                    "relatedSpdxElement": spdx_pkg["SPDXID"],
                    "relationshipType": "DEPENDS_ON"
                })

        # 5. Process Build Artifacts (Outputs)
        all_built_packages = []
        
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

                # Add file components if enabled
                if self.include_file_components:
                    file_spdx_objs = self.create_file_components(rpm_path, spdx_pkg["SPDXID"])
                    for file_obj in file_spdx_objs:
                        document["files"].append(file_obj)
                        document["relationships"].append({
                            "spdxElementId": spdx_pkg["SPDXID"],
                            "relatedSpdxElement": file_obj["SPDXID"],
                            "relationshipType": "CONTAINS"
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

    # pylint: disable=too-many-locals,too-many-branches,too-many-statements
    def create_spdx_package_from_rpm(self, rpm_path, distro_obj):
        """Creates an SPDX Package from an RPM file, including all header metadata."""
        pkg_data = self.rpm_helper.get_rpm_metadata(rpm_path)
        if not pkg_data:
            self.buildroot.root_log.debug(f"[SBOM] FAILED to get metadata for {rpm_path}, skipping SPDX package")
            return None

        name = pkg_data.get("name")
        version = pkg_data.get("version")
        release = pkg_data.get("release")
        full_version = f"{version}-{release}" if release else version

        safe_name = re.sub(r'[^a-zA-Z0-9.-]', '-', name)
        safe_ver = re.sub(r'[^a-zA-Z0-9.-]', '-', full_version)
        spdx_id = f"SPDXRef-Package-{safe_name}-{safe_ver}"

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

        # GPG Signature Information
        signature = self.rpm_helper.get_rpm_signature(rpm_path)
        if signature:
            metadata_fields.append(f"GPG Signature: {signature}")

        if metadata_fields:
            package["comment"] = " | ".join(metadata_fields)

        # Checksums
        rpm_hash = pkg_data.get("sha256")
        if not rpm_hash or rpm_hash == "(none)":
            rpm_hash = self.rpm_helper.hash_file(rpm_path)
            
        if rpm_hash:
            package["checksums"] = [{"algorithm": "SHA256", "checksumValue": rpm_hash}]

        # External References (CPE and PURL)
        external_refs = []
        vendor = pkg_data.get("vendor")
        cpe = self.rpm_helper.generate_cpe(name, version, vendor=vendor)
        if cpe:
            external_refs.append({
                "referenceCategory": "SECURITY",
                "referenceType": "cpe23Type",
                "referenceLocator": cpe
            })
            
        purl = self.rpm_helper.generate_purl(name, full_version, distro_obj, pkg_data.get("arch"))
        if purl:
            external_refs.append({
                "referenceCategory": "PACKAGE-MANAGER",
                "referenceType": "purl",
                "referenceLocator": purl
            })

        if external_refs:
            package["externalRefs"] = external_refs

        return package

    def create_spdx_package_from_dict(self, pkg_data):
        """Creates an SPDX Package from a dictionary (e.g. toolchain)."""
        name = pkg_data.get("name")
        version = pkg_data.get("version")
        if not name or not version:
            self.buildroot.root_log.debug(
                "[SBOM] Skipping toolchain package due to missing name/version"
            )
            return None

        safe_name = re.sub(r'[^a-zA-Z0-9.-]', '-', name)
        safe_ver = re.sub(r'[^a-zA-Z0-9.-]', '-', version)
        spdx_id = f"SPDXRef-Package-{safe_name}-{safe_ver}"

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

        # Checksums - REMOVED per user request to only have hashes for files contained in RPM
        # (Follows CycloneDX parity where external toolchain hashes are omitted)
        # checksum = pkg_data.get("checksum")
        # if checksum and not checksum.startswith("error"):
        #     alg = "SHA256" if len(checksum) == 64 else "SHA1"
        #     package["checksums"] = [{
        #         "algorithm": alg,
        #         "checksumValue": checksum
        #     }]

        return package

    def create_spdx_file(self, file_data, parent_pkg_id=None):
        """Creates an SPDX File from file metadata."""
        filename = file_data.get("filename")
        if not filename:
            return None

        safe_name = re.sub(r'[^a-zA-Z0-9.-]', '-', filename)
        # Use a more unique ID if parent is provided
        if parent_pkg_id:
            parent_suffix = parent_pkg_id.split("-")[-1]
            spdx_id = f"SPDXRef-File-{safe_name}-{parent_suffix}"
        else:
            spdx_id = f"SPDXRef-File-{safe_name}"

        file_obj = {
            "fileName": f"./{filename}",
            "SPDXID": spdx_id,
            "licenseConcluded": "NOASSERTION",
            "copyrightText": "NOASSERTION"
        }

        sha256 = file_data.get("sha256")
        if sha256:
            file_obj["checksums"] = [{"algorithm": "SHA256", "checksumValue": sha256}]

        # Store GPG flag as a comment if present
        if file_data.get("digital_signature"):
            file_obj["comment"] = f"Signature Status: {file_data['digital_signature']}"

        return file_obj

    def create_file_components(self, rpm_path, parent_spdx_id):
        """Extracts file list from an RPM and creates SPDX File objects."""
        file_info = self.rpm_helper.get_rpm_file_info(rpm_path) or {}
        spdx_files = []

        for filename in sorted(file_info.keys()):
            f_data = file_info[filename]
            # Ensure filename is in the data dict for create_spdx_file
            f_data["filename"] = filename
            
            # Filtering logic (man pages, debug files)
            if not self.include_debug_files and (".build-id" in filename or ".debug" in filename):
                continue
            if not self.include_man_pages and ("/usr/share/man" in filename or "/usr/share/info" in filename):
                continue

            f_obj = self.create_spdx_file(f_data, parent_pkg_id=parent_spdx_id)
            if f_obj:
                spdx_files.append(f_obj)

        return spdx_files
