# -*- coding: utf-8 -*-
# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# SPDX-License-Identifier: GPL-2.0-or-later
# Written by Scott R. Shinn <scott@atomicorp.com>
# Copyright (C) 2026, Atomicorp, Inc.
"""
CycloneDX generation functions for the SBOM generator plugin.
"""

import os
import re
import uuid
import hashlib
from datetime import datetime, timezone

from mockbuild.sbom_utils import should_include_rpm_file, resolve_rpm_dependency


class CycloneDxGenerator:
    """Helper class for generating CycloneDX documents."""

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

    def create_built_package_component(
        self, rpm_path, distro_obj, _source_components=None
    ):
        """Creates a CycloneDX component for a built RPM package."""
        package_data = self.rpm_helper.get_rpm_metadata(rpm_path)
        if not package_data:
            self.buildroot.root_log.debug(
                "[SBOM] FAILED to get metadata for %s, skipping component", rpm_path
            )
            return None

        package_name = package_data.get("name")
        version = package_data.get("version")
        release = package_data.get("release")
        arch = package_data.get("arch")

        # Combine version and release
        full_version = f"{version}-{release}" if release else version

        # Generate PURL and bom-ref
        purl = self.rpm_helper.generate_purl(
            package_name, full_version, distro_obj, arch,
            epoch=package_data.get("epoch"),
        )
        bom_ref = purl

        component = {
            "type": "library",
            "bom-ref": bom_ref,
            "name": package_name,
            "version": full_version,
            "purl": purl,
        }

        # Single shared properties list so later metadata does not drop CPE/etc.
        properties = []

        # Add external references (CPE) — heuristic only when enabled
        if self.conf.get("generate_cpe", False):
            vendor = package_data.get("vendor")
            cpe, confidence = self.rpm_helper.generate_cpe(
                package_name, version, vendor=vendor
            )
            if cpe:
                component["externalReferences"] = [
                    {
                        "type": "other",
                        "comment": f"CPE 2.3 ({confidence})",
                        "url": cpe
                    }
                ]
                properties.append({
                    "name": "mock:cpe:confidence",
                    "value": confidence,
                })

        # Add license information
        license_str = package_data.get("license")
        if license_str and license_str != "(none)":
            component["licenses"] = [{"expression": license_str}]

        # Add supplier information (from Packager field)
        packager = package_data.get("packager")
        if packager and packager != "(none)":
            component["supplier"] = {"name": packager}

        # Add properties for RPM metadata
        properties.append({
            "name": "mock:rpm:filename",
            "value": os.path.basename(rpm_path)
        })

        vendor = package_data.get("vendor")
        if vendor and vendor != "(none)":
            properties.append({"name": "mock:rpm:vendor", "value": vendor})

        packager = package_data.get("packager")
        if packager and packager != "(none)":
            properties.append({"name": "mock:rpm:packager", "value": packager})

        buildhost = package_data.get("buildhost")
        if buildhost and buildhost != "(none)":
            properties.append({"name": "mock:rpm:buildhost", "value": buildhost})

        buildtime_iso = self.format_epoch_timestamp(package_data.get("buildtime"))
        if buildtime_iso:
            properties.append({"name": "mock:rpm:buildtime", "value": buildtime_iso})

        group = package_data.get("group")
        if group and group != "(none)":
            properties.append({"name": "mock:rpm:group", "value": group})

        epoch_val = package_data.get("epoch")
        if epoch_val and epoch_val != "(none)":
            properties.append({"name": "mock:rpm:epoch", "value": epoch_val})

        distribution = package_data.get("distribution")
        if distribution and distribution != "(none)":
            properties.append({"name": "mock:rpm:distribution", "value": distribution})

        url = package_data.get("url")
        if url and url != "(none)":
            component["externalReferences"] = component.get("externalReferences", [])
            component["externalReferences"].append({"type": "website", "url": url})

        summary = package_data.get("summary")
        if summary and summary != "(none)":
            component["description"] = summary

        # Add GPG signature information if available (verified when possible)
        sig_info = self.rpm_helper.verify_rpm_signature(rpm_path)
        if sig_info:
            sig_props = self.signature_info_to_properties(sig_info)
            properties.extend(sig_props)

        # Package-level integrity hash: always the full RPM file digest.
        # Header SHA256 (RPMTAG_SHA256HEADER) is not the artifact checksum.
        host_path = self.rpm_helper.host_path(rpm_path)
        pkg_hash = None
        if os.path.isfile(host_path):
            pkg_hash = self.rpm_helper.hash_file(host_path)
        header_sha = package_data.get("sha256")
        if header_sha and header_sha not in (None, "", "(none)"):
            properties.append({
                "name": "mock:rpm:sha256header",
                "value": header_sha,
            })
        if properties:
            component["properties"] = properties
        elif "properties" in component and not component["properties"]:
            del component["properties"]

        if pkg_hash and pkg_hash != "(none)":
            component["hashes"] = [{"alg": "SHA-256", "content": pkg_hash}]

        return component

    def parse_signature_to_properties(self, signature_string):
        """Parses RPM signature string into CycloneDX properties (unverified)."""
        info = self.rpm_helper.parse_signature_data(signature_string)
        return self.signature_info_to_properties(info)

    def signature_info_to_properties(self, signature_info):
        """Converts signature info dict to CycloneDX properties."""
        properties = []
        sig_type = signature_info.get("signature_type", "unsigned")
        properties.append({"name": "mock:signature:type", "value": sig_type})

        status = signature_info.get("signature_status", "unsigned")
        properties.append({"name": "mock:signature:status", "value": status})
        # signature_valid is True only when cryptographically verified
        properties.append({
            "name": "mock:signature:valid",
            "value": str(bool(signature_info.get("signature_valid"))).lower(),
        })

        if status != "unsigned":
            algorithm = signature_info.get("signature_algorithm")
            if algorithm:
                properties.append({"name": "mock:signature:algorithm", "value": algorithm})

            key_id = signature_info.get("signature_key")
            if key_id:
                properties.append({"name": "mock:signature:key", "value": key_id})

            sig_date = signature_info.get("signature_date")
            if sig_date:
                properties.append({"name": "mock:signature:date", "value": sig_date})

            raw_data = signature_info.get("raw_signature_data")
            if raw_data:
                properties.append({"name": "mock:signature:raw", "value": raw_data})

        return properties

    def create_cyclonedx_document(self, serial_seed=None):
        """Initializes the base CycloneDX JSON structure.

        When SOURCE_DATE_EPOCH is set and serial_seed is provided, the
        serialNumber is a deterministic UUIDv5 so rebuilds are bit-stable.
        """
        epoch = os.environ.get("SOURCE_DATE_EPOCH")
        if epoch and str(epoch).isdigit() and serial_seed:
            serial = uuid.uuid5(uuid.NAMESPACE_URL, f"mock-sbom:{epoch}:{serial_seed}")
        else:
            serial = uuid.uuid4()
        return {
            "bomFormat": "CycloneDX",
            "specVersion": "1.6",
            "serialNumber": f"urn:uuid:{serial}",
            "version": 1,
            "metadata": {},
            "components": [],
            "dependencies": [],
            "formulation": [],
        }

    def generate_file_bom_ref(self, package_name, package_version, file_path):
        """Generates a unique but stable bom-ref for a file.

        Sanitized components stay human-readable; a short digest of the
        original ``(name, version, path)`` tuple prevents collisions when
        distinct unsanitized inputs collapse to the same safe string.
        """
        safe_name = re.sub(r'[^a-zA-Z0-9.-]', '-', package_name)
        safe_version = re.sub(r'[^a-zA-Z0-9.-]', '-', package_version)
        safe_path = re.sub(r'[^a-zA-Z0-9.-]', '-', file_path.lstrip('/'))
        seed = f"{package_name}\0{package_version}\0{file_path}".encode("utf-8")
        try:
            digest = hashlib.sha1(seed, usedforsecurity=False).hexdigest()[:12]
        except TypeError:
            digest = hashlib.sha1(seed).hexdigest()[:12]
        return f"file:{safe_name}-{safe_version}:{safe_path}:{digest}"

    def add_source_components(self, _bom, source_files):
        """Adds source files (from spec) to the components list."""
        source_components = []
        source_component_entries = []
        for src_file in source_files:
            file_comp = self.create_source_file_component(src_file)
            _bom["components"].append(file_comp)
            source_components.append(file_comp)
            source_component_entries.append({
                "filename": src_file["filename"],
                "bom-ref": file_comp["bom-ref"]
            })
        return source_components, source_component_entries

    def create_source_file_component(self, source_file):
        """Creates a CycloneDX component for a source file."""
        filename = source_file["filename"]
        sha256 = source_file.get("sha256")
        sig = source_file.get("digital_signature")
        source_type = source_file.get("source_type")
        is_srpm = (
            source_type == "source_rpm"
            or (filename or "").endswith(".src.rpm")
        )

        safe_name = re.sub(r'[^a-zA-Z0-9.-]', '-', filename)
        try:
            name_digest = hashlib.sha1(
                (filename or "").encode("utf-8"), usedforsecurity=False
            ).hexdigest()[:12]
        except TypeError:
            name_digest = hashlib.sha1((filename or "").encode("utf-8")).hexdigest()[:12]
        hash_suffix = sha256[:8] if sha256 else "unknown"
        bom_ref = f"source-file:{safe_name}-{hash_suffix}:{name_digest}"

        if is_srpm:
            type_value = "source_rpm"
        elif self.is_patch_file(filename):
            type_value = "patch"
        else:
            type_value = "source"

        comp = {
            "type": "file",
            "bom-ref": bom_ref,
            "name": filename,
            "properties": [
                {"name": "mock:source:type", "value": type_value}
            ]
        }
        if is_srpm:
            comp["properties"].append({
                "name": "mock:rpm:filename",
                "value": filename,
            })
        if sha256:
            comp["hashes"] = [{"alg": "SHA-256", "content": sha256}]
        if isinstance(sig, dict):
            comp["properties"].extend(self.signature_info_to_properties(sig))
        elif sig:
            # Legacy string form from older prebuild snapshots
            if isinstance(sig, str) and ("Key ID" in sig or "RSA/" in sig or "GPG" in sig):
                comp["properties"].extend(self.parse_signature_to_properties(sig))
            else:
                comp["properties"].append({"name": "mock:signature:info", "value": str(sig)})

        return comp

    def is_patch_file(self, filename):
        """Determines if a file is a patch file based on common extensions."""
        patch_extensions = ['.patch', '.diff']
        return any(filename.lower().endswith(ext) for ext in patch_extensions)

    def format_epoch_timestamp(self, epoch_value):
        """Converts an epoch integer to an ISO 8601 timestamp string."""
        try:
            val_int = int(epoch_value)
            dt = datetime.fromtimestamp(val_int, timezone.utc)
            return dt.isoformat()
        except (ValueError, TypeError):
            return ""

    def create_dependency(self, bom_ref, dependencies, component_map, distro_obj,
                          provides_map=None):
        """Creates a dependency entry mapping raw requires to parsed bom-refs."""
        dep_entry = {
            "ref": bom_ref,
            "dependsOn": []
        }
        for raw_dep in dependencies:
            target_ref = self.dependency_to_bom_ref(
                raw_dep, component_map, distro_obj, provides_map=provides_map
            )
            if target_ref and target_ref not in dep_entry["dependsOn"] and target_ref != bom_ref:
                dep_entry["dependsOn"].append(target_ref)

        return dep_entry if dep_entry["dependsOn"] else None

    def dependency_to_bom_ref(self, dependency_string, component_map, _distro,
                              provides_map=None):
        """
        Attempts to map a raw RPM dependency string (e.g., 'libc.so.6', 'bash >= 4.0')
        to a concrete bom-ref in the component_map / provides_map.

        ``component_map`` keys are lowercased binary package names; values must
        be the same bom-ref/purl already used on the component (including
        arch/epoch). Source RPMs are intentionally excluded from the map.
        ``provides_map`` maps lowercased capability names to bom-refs.
        """
        return resolve_rpm_dependency(
            dependency_string, component_map, provides_map=provides_map
        )

    def process_built_packages(self, bom, rpm_files, build_dir, distro_id,
                               source_component_entries, build_subject_name,
                               build_toolchain_packages, toolchain_bom_refs):
        """Processes binary RPMs and creates structured CycloneDX components and dependencies."""
        built_package_bom_refs = []
        all_built_components = []
        component_map = {}
        provides_map = {}
        primary_rpm_metadata = None
        # (rpm_path, bom_ref) for dependency resolution after all packages are registered
        pending_deps = []

        # Build component map from toolchain packages — PURLs must match
        # create_toolchain_component (arch + epoch) or dependsOn refs dangle.
        toolchain_names = []
        for toolchain_pkg in build_toolchain_packages:
            pkg_name = toolchain_pkg.get("name")
            pkg_version = toolchain_pkg.get("version")
            if pkg_name and pkg_version:
                purl = self.rpm_helper.generate_purl(
                    pkg_name, pkg_version, distro_id,
                    arch=toolchain_pkg.get("arch"),
                    epoch=toolchain_pkg.get("epoch"),
                )
                component_map[pkg_name.lower()] = purl
                toolchain_names.append(pkg_name)

        # Index installed Provides → package name, then remap to bom-refs.
        installed_provides = self.rpm_helper.get_installed_provides_map(
            package_names=toolchain_names or None
        )
        for capability, pkg_name in installed_provides.items():
            bom_ref = component_map.get(pkg_name)
            if bom_ref:
                provides_map.setdefault(capability, bom_ref)

        # Pass 1: create every RPM component and register it in component_map
        # before any Requires → bom-ref resolution.
        for rpm_file in rpm_files:
            rpm_path = os.path.join(build_dir, rpm_file)
            component = self.create_built_package_component(
                rpm_path, distro_id, source_component_entries
            )
            if not component:
                continue

            bom_ref = component.get("bom-ref")
            package_name = component.get("name")
            package_version = component.get("version")

            if bom_ref:
                built_package_bom_refs.append(bom_ref)
                # Requires resolution must target binary RPMs. SRPMs share the
                # package name and would otherwise displace the binary bom-ref.
                if package_name and not rpm_file.endswith(".src.rpm"):
                    component_map[package_name.lower()] = bom_ref
                    for capability in self.rpm_helper.get_rpm_provides(rpm_path) or []:
                        cap_key = capability.lower()
                        provides_map.setdefault(cap_key, bom_ref)
                        bare = capability.split("(", 1)[0].strip().lower()
                        if bare:
                            provides_map.setdefault(bare, bom_ref)
                pending_deps.append((rpm_path, bom_ref))

            bom["components"].append(component)

            # Determine primary RPM metadata
            if not primary_rpm_metadata:
                if not package_name or 'debuginfo' not in package_name.lower():
                    primary_rpm_metadata = self.rpm_helper.get_rpm_metadata(rpm_path)
            else:
                current_name = primary_rpm_metadata.get('name', '').lower()
                is_current_debuginfo = 'debuginfo' in current_name
                should_replace = False
                if (is_current_debuginfo and package_name and
                        'debuginfo' not in package_name.lower()):
                    should_replace = True
                elif (build_subject_name and package_name and
                      package_name.lower() == build_subject_name.lower()):
                    should_replace = True

                if should_replace:
                    self.buildroot.root_log.debug(
                        "[SBOM] Selecting %s as primary metadata source", package_name
                    )
                    primary_rpm_metadata = self.rpm_helper.get_rpm_metadata(rpm_path)

            # File components (local file→package edges do not need the full map)
            if package_name and package_version and self.include_file_components:
                rpm_cpe = None
                for ext_ref in component.get("externalReferences", []):
                    if "CPE 2.3" in (ext_ref.get("comment") or ""):
                        rpm_cpe = ext_ref.get("url")

                rpm_gpg = None
                for prop in component.get("properties", []):
                    if prop.get("name") == "mock:signature:key":
                        rpm_gpg = prop.get("value")

                file_components = self.create_file_components(
                    rpm_path, package_name, package_version,
                    rpm_cpe=rpm_cpe, rpm_gpg=rpm_gpg
                )

                if file_components:
                    if "components" not in component:
                        component["components"] = []

                    for file_comp in file_components:
                        file_comp["scope"] = "required"
                        component["components"].append(file_comp)

                        if self.should_include_file_dependency(file_comp.get("name", "")):
                            bom["dependencies"].append({
                                "ref": file_comp["bom-ref"],
                                "dependsOn": [bom_ref]
                            })

                    component["components"].sort(key=lambda x: x.get("name", ""))

            all_built_components.append(component)

        # Pass 2: resolve package dependencies against the complete component_map
        for rpm_path, bom_ref in pending_deps:
            dependencies = self.rpm_helper.get_rpm_dependencies(rpm_path) or []
            runtime_dependency = self.create_dependency(
                bom_ref, dependencies, component_map, distro_id,
                provides_map=provides_map,
            )

            all_depends_on = []
            if runtime_dependency and runtime_dependency.get("dependsOn"):
                all_depends_on.extend(runtime_dependency.get("dependsOn"))

            if self.include_toolchain_dependencies and toolchain_bom_refs:
                for t_ref in toolchain_bom_refs:
                    if t_ref not in all_depends_on:
                        all_depends_on.append(t_ref)

            all_depends_on = sorted(list(set(all_depends_on)))
            # Always record the output package in the dependency graph so
            # auditors can verify every build-output appears as a subject.
            bom["dependencies"].append({
                "ref": bom_ref,
                "dependsOn": all_depends_on,
            })

        return built_package_bom_refs, primary_rpm_metadata, all_built_components

    # pylint: disable=too-many-arguments,too-many-locals,too-many-branches
    # pylint: disable=too-many-statements,too-many-positional-arguments
    def finalize_bom_metadata(self, bom, primary_rpm_metadata, built_package_bom_refs,
                                build_subject_name, build_subject_version,
                                build_subject_release, distro_id, spec_metadata=None):
        """Finalizes BOM metadata, sets the primary component, and adds RPM properties."""
        # Add BuildRequires and Requires from spec if available
        if spec_metadata:
            metadata_props = []
            build_reqs = spec_metadata.get("build_requires", [])
            if build_reqs:
                metadata_props.append({
                    "name": "mock:spec:build_requires",
                    "value": ",".join(build_reqs)
                })

            reqs = spec_metadata.get("requires", [])
            if reqs:
                metadata_props.append({
                    "name": "mock:spec:requires",
                    "value": ",".join(reqs)
                })

            if metadata_props:
                bom["metadata"]["properties"] = bom["metadata"].get("properties", [])
                bom["metadata"]["properties"].extend(metadata_props)

        if primary_rpm_metadata:
            if "properties" not in bom["metadata"]:
                bom["metadata"]["properties"] = []
            rpm_props = bom["metadata"]["properties"]
            for key, prop_name in [("buildhost", "mock:rpm:buildhost"),
                                  ("buildtime", "mock:rpm:buildtime"),
                                  ("group", "mock:rpm:group"),
                                  ("epoch", "mock:rpm:epoch"),
                                  ("distribution", "mock:rpm:distribution")]:
                val = primary_rpm_metadata.get(key)
                if val and val != "(none)" and (key != "epoch" or val.strip()):
                    rpm_props.append({"name": prop_name, "value": val})

            vendor = primary_rpm_metadata.get("vendor")
            if vendor and vendor == "(none)":
                vendor = None

            packager = primary_rpm_metadata.get("packager")
            if packager and packager != "(none)":
                bom["metadata"]["supplier"] = {"name": packager}
        else:
            vendor = None

        if built_package_bom_refs:
            if len(built_package_bom_refs) == 1:
                primary_ref = built_package_bom_refs[0]
                primary_component = next((c for c in bom["components"]
                                        if c.get("bom-ref") == primary_ref), None)
                if primary_component:
                    component_obj = {
                        "type": primary_component.get("type", "application"),
                        "name": primary_component.get("name"),
                        "version": primary_component.get("version"),
                        "bom-ref": primary_ref,
                        "purl": primary_component.get("purl")
                    }
                    if vendor:
                        # RPM Vendor describes the component, not the BOM author.
                        component_obj["manufacturer"] = {"name": vendor}
                    if primary_component.get("description"):
                        component_obj["description"] = primary_component.get("description")
                    elif primary_rpm_metadata:
                        summary = primary_rpm_metadata.get("summary")
                        if summary and summary != "(none)":
                            component_obj["description"] = summary

                    external_refs = []
                    if primary_rpm_metadata:
                        sourcerpm = primary_rpm_metadata.get("sourcerpm")
                        if sourcerpm and sourcerpm != "(none)":
                            external_refs.append({"type": "distribution", "url": sourcerpm})
                        url = primary_rpm_metadata.get("url")
                        if url and url != "(none)":
                            external_refs.append({"type": "website", "url": url})
                    if external_refs:
                        component_obj["externalReferences"] = external_refs

                    if primary_component.get("licenses"):
                        component_obj["licenses"] = primary_component.get("licenses")
                    elif primary_rpm_metadata:
                        lic = primary_rpm_metadata.get("license")
                        if lic and lic != "(none)":
                            component_obj["licenses"] = [{"expression": lic}]
                    bom["metadata"]["component"] = component_obj
            else:
                first_pkg = next((c for c in bom["components"]
                                 if c.get("bom-ref") == built_package_bom_refs[0]), None)
                if first_pkg:
                    aggregate_name = build_subject_name or first_pkg.get("name", "unknown")
                    aggregate_version = None
                    if build_subject_version and build_subject_release:
                        aggregate_version = f"{build_subject_version}-{build_subject_release}"
                    elif primary_rpm_metadata:
                        v = primary_rpm_metadata.get("version")
                        r = primary_rpm_metadata.get("release")
                        if v and r:
                            aggregate_version = f"{v}-{r}"
                    if not aggregate_version:
                        aggregate_version = first_pkg.get("version", "unknown")

                    description = (
                        f"Build output containing {len(built_package_bom_refs)} package(s)"
                    )
                    if primary_rpm_metadata:
                        summary = primary_rpm_metadata.get("summary")
                        if summary and summary != "(none)":
                            description = f"{summary} ({description})"

                    component_obj = {
                        "type": "application",
                        "name": aggregate_name,
                        "version": aggregate_version,
                        "bom-ref": f"build-output:{aggregate_name}",
                        "description": description
                    }
                    if vendor:
                        component_obj["manufacturer"] = {"name": vendor}
                    if primary_rpm_metadata:
                        lic = primary_rpm_metadata.get("license")
                        if lic and lic != "(none)":
                            component_obj["licenses"] = [{"expression": lic}]
                    elif spec_metadata and spec_metadata.get("license"):
                        component_obj["licenses"] = [{"expression": spec_metadata["license"]}]

                    if aggregate_name and aggregate_version:
                        component_obj["purl"] = self.rpm_helper.generate_purl(
                            aggregate_name, aggregate_version, distro_id
                        )
                    bom["metadata"]["component"] = component_obj

    # pylint: disable=too-many-locals,too-many-branches,too-many-statements

    def finalize_dependencies(self, bom, source_component_entries,
                                build_toolchain_packages,
                                built_package_bom_refs, toolchain_bom_refs,
                                source_components=None,
                                toolchain_components=None,
                                all_built_components=None):
        """Wire dependencies and emit a CycloneDX 1.6 formulation.

        Real packages/files stay in ``components`` (scanner-friendly flat list).
        Build Inputs / Toolchain / Outputs roles are described in ``formulation``
        instead of nested grouping nodes under metadata.component.
        """
        # Signature props come from create_toolchain_component; package list
        # is retained for call-site API compatibility only.
        _ = build_toolchain_packages

        primary_ref = None
        if bom.get("metadata") and bom["metadata"].get("component"):
            primary_ref = bom["metadata"]["component"].get("bom-ref")

        if not primary_ref:
            return

        # Flatten toolchain into the top-level component inventory.
        # Signature properties are attached in create_toolchain_component from
        # the exact package instance (NEVRA-aware); do not re-lookup by name.
        if toolchain_components:
            for comp in toolchain_components:
                comp["scope"] = "excluded"
                comp.setdefault("properties", []).append({
                    "name": "mock:role",
                    "value": "build-toolchain",
                })
                bom["components"].append(comp)

        if source_components:
            for comp in source_components:
                # Already in bom["components"] via add_source_components; tag role.
                props = comp.setdefault("properties", [])
                if not any(p.get("name") == "mock:role" for p in props):
                    props.append({"name": "mock:role", "value": "build-input"})

        if all_built_components:
            for comp in all_built_components:
                props = comp.setdefault("properties", [])
                if not any(p.get("name") == "mock:role" for p in props):
                    props.append({"name": "mock:role", "value": "build-output"})

        # Primary depends on inputs + toolchain + outputs (by bom-ref).
        # Exclude self-refs (single-package builds reuse the package bom-ref as
        # metadata.component) and merge into any existing dependency entry.
        depends_on = []
        input_refs = [
            e["bom-ref"] for e in source_component_entries if e.get("bom-ref")
        ]
        if self.include_source_dependencies:
            depends_on.extend(input_refs)
        if self.include_toolchain_dependencies:
            depends_on.extend(toolchain_bom_refs or [])
        depends_on.extend(built_package_bom_refs or [])
        depends_on = sorted({ref for ref in depends_on if ref and ref != primary_ref})
        if depends_on:
            existing = next(
                (
                    dep for dep in bom.get("dependencies", [])
                    if dep.get("ref") == primary_ref
                ),
                None,
            )
            if existing:
                existing["dependsOn"] = sorted(
                    set(existing.get("dependsOn") or []) | set(depends_on)
                )
            else:
                bom["dependencies"].append({
                    "ref": primary_ref,
                    "dependsOn": depends_on,
                })

        # CycloneDX 1.6 formulation: describe the build without grouping nodes
        workflow = {
            "bom-ref": "mock:workflow:rpmbuild",
            "uid": "mock-rpmbuild",
            "name": "Mock RPM Build",
            "taskTypes": ["build"],
            "inputs": [
                {"resource": {"ref": ref}}
                for ref in sorted(set(input_refs))
                if self.include_source_dependencies
            ],
            "outputs": [
                {
                    "type": "artifact",
                    "resource": {"ref": ref},
                }
                for ref in sorted(set(built_package_bom_refs or []))
            ],
            "properties": [
                {
                    "name": "mock:toolchain:count",
                    "value": str(len(toolchain_bom_refs or [])),
                },
                {
                    "name": "mock:toolchain:note",
                    "value": (
                        "Build toolchain packages are listed in components[] "
                        "with scope=excluded and mock:role=build-toolchain"
                    ),
                },
            ],
        }

        bom["formulation"] = [{
            "bom-ref": "mock:formulation:build",
            "components": [
                {
                    "type": "application",
                    "bom-ref": "mock:tool:mock-sbom-generator",
                    "name": "mock-sbom-generator",
                    "description": "Mock SBOM generator capturing build provenance",
                }
            ],
            "workflows": [workflow],
        }]
        # Drop legacy misspelled key if a prior partial write left it
        bom.pop("formulations", None)



    def create_toolchain_component(self, toolchain_pkg, distro_obj):
        """Creates a CycloneDX component for a build toolchain package."""
        package_name = toolchain_pkg.get("name")
        version = toolchain_pkg.get("version")

        if not package_name or not version:
            return None

        # Generate PURL and bom-ref
        purl = self.rpm_helper.generate_purl(
            package_name, version, distro_obj,
            arch=toolchain_pkg.get("arch"),
            epoch=toolchain_pkg.get("epoch"),
        )
        bom_ref = purl

        component = {
            "type": "library",
            "bom-ref": bom_ref,
            "name": package_name,
            "version": version,
            "purl": purl,
            "properties": [],
        }

        # Add CPE only when explicitly enabled
        cpe = toolchain_pkg.get("cpe")
        if cpe:
            component["externalReferences"] = [
                {
                    "type": "other",
                    "comment": f"CPE 2.3 ({toolchain_pkg.get('cpe_confidence', 'heuristic')})",
                    "url": cpe
                }
            ]
            component["properties"].append({
                "name": "mock:cpe:confidence",
                "value": toolchain_pkg.get("cpe_confidence", "heuristic"),
            })

        # Add license
        license_str = toolchain_pkg.get("licenseDeclared")
        if license_str and license_str != "(none)":
            component["licenses"] = [
                {
                    "expression": license_str
                }
            ]

        # Repo/download URL from buildroot lock / repoquery when available
        url = toolchain_pkg.get("url")
        if url:
            component.setdefault("externalReferences", []).append({
                "type": "distribution",
                "url": url,
            })

        # Package-level header digest when available from rpmdb
        checksum = toolchain_pkg.get("checksum")
        if checksum and checksum != "(none)":
            component["hashes"] = [{"alg": "SHA-256", "content": checksum}]

        # Signature metadata from this exact package instance (arch/epoch-safe).
        signature_info = toolchain_pkg.get("digital_signature") or {}
        if signature_info:
            sig_props = self.signature_info_to_properties(signature_info)
            component["properties"].extend(
                [p for p in sig_props if p["name"] != "mock:signature:raw"]
            )
        build_date = signature_info.get("build_date")
        if build_date:
            component["properties"].append({
                "name": "mock:build:date",
                "value": build_date
            })

        if not component["properties"]:
            del component["properties"]

        return component


    def create_file_components(self, rpm_path, package_name, package_version,
                               rpm_cpe=None, rpm_gpg=None):
        """Creates file components for all files in an RPM package."""
        if not self.include_file_components:
            return []

        file_info = self.rpm_helper.get_rpm_file_info(rpm_path)
        if not file_info:
            return []

        file_list = sorted(file_info.keys())

        file_components = []
        for file_path in file_list:
            if not file_path or not file_path.strip():
                continue

            if not self.should_include_file(file_path):
                continue

            file_data = file_info.get(file_path, {})
            file_hash = file_data.get("hash")
            algo_id = file_data.get("algo")

            bom_ref = self.generate_file_bom_ref(package_name, package_version, file_path)
            component = {
                "type": "file",
                "bom-ref": bom_ref,
                "name": file_path
            }

            # Add hash only when algorithm is known — never default to SHA-256.
            if file_hash:
                algo_map = {
                    8: "SHA-256",
                    10: "SHA-512",
                    1: "MD5",
                    2: "SHA-1",
                    9: "SHA-384",
                    12: "SHA3-256",
                    14: "SHA3-512",
                    # RPM algo 11 (SHA-224) is not in CycloneDX 1.6 hash alg enum.
                }
                alg_name = None
                digest_algo = file_data.get("digest_algorithm")
                if digest_algo:
                    key = str(digest_algo).upper().replace("_", "").replace("-", "")
                    name_map = {
                        "SHA256": "SHA-256",
                        "SHA512": "SHA-512",
                        "MD5": "MD5",
                        "SHA1": "SHA-1",
                        "SHA384": "SHA-384",
                        "SHA3256": "SHA3-256",
                        "SHA3512": "SHA3-512",
                    }
                    alg_name = name_map.get(key)
                if not alg_name:
                    alg_name = algo_map.get(algo_id)
                if alg_name:
                    component["hashes"] = [{
                        "alg": alg_name,
                        "content": file_hash,
                    }]

            # Add properties for file metadata
            properties = []
            if file_data.get("permissions"):
                properties.append({
                    "name": "mock:file:permissions",
                    "value": file_data["permissions"]
                })
            if file_data.get("owner"):
                properties.append({
                    "name": "mock:file:owner",
                    "value": file_data["owner"]
                })
            if file_data.get("group"):
                properties.append({
                    "name": "mock:file:group",
                    "value": file_data["group"]
                })

            if rpm_cpe:
                properties.append({
                    "name": "mock:package:cpe",
                    "value": rpm_cpe
                })
            if rpm_gpg:
                properties.append({
                    "name": "mock:package:gpg:key",
                    "value": rpm_gpg
                })

            if properties:
                component["properties"] = properties

            file_components.append(component)

        return file_components


    def should_include_file(self, file_path):
        """Shared file filter used by CDX (and mirrored by SPDX)."""
        return should_include_rpm_file(
            file_path,
            include_debug_files=self.include_debug_files,
            include_man_pages=self.include_man_pages,
        )

    def should_include_file_dependency(self, file_path):
        """Determine if a file should have a dependency entry."""
        if not self.include_file_dependencies:
            return False
        return self.should_include_file(file_path)
