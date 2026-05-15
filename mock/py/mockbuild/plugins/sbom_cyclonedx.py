# -*- coding: utf-8 -*-
# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# License: GPL2 or later see COPYING
# Written by Scott R. Shinn <scott@atomicorp.com>
# Copyright (C) 2026, Atomicorp, Inc.

import os
import re
import uuid
from datetime import datetime, timezone

"""
CycloneDX generation functions for the SBOM generator plugin.
"""


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
        self.include_toolchain_dependencies = self.conf.get(
            "include_toolchain_dependencies", False
        )

    def create_built_package_component(
        self, rpm_path, distro_obj, _source_components=None
    ):
        """Creates a CycloneDX component for a built RPM package."""
        package_data = self.rpm_helper.get_rpm_metadata(rpm_path)
        if not package_data:
            self.buildroot.root_log.debug(f"[SBOM] FAILED to get metadata for {rpm_path}, skipping component")
            return None

        package_name = package_data.get("name")
        version = package_data.get("version")
        release = package_data.get("release")
        arch = package_data.get("arch")

        # Combine version and release
        full_version = f"{version}-{release}" if release else version

        # Generate PURL and bom-ref
        purl = self.rpm_helper.generate_purl(package_name, full_version, distro_obj, arch)
        bom_ref = purl

        # Determine component type (application vs library)
        component_type = "library"

        component = {
            "type": component_type,
            "bom-ref": bom_ref,
            "name": package_name,
            "version": full_version,
            "purl": purl
        }

        # Add external references (CPE)
        vendor = package_data.get("vendor")
        cpe = self.rpm_helper.generate_cpe(package_name, version, vendor=vendor)
        if cpe:
            component["externalReferences"] = [
                {
                    "type": "other",
                    "comment": "CPE 2.3",
                    "url": cpe
                }
            ]

        # Add license information
        license_str = package_data.get("license")
        if license_str and license_str != "(none)":
            component["licenses"] = [{"expression": license_str}]

        # Add supplier information (from Packager field)
        packager = package_data.get("packager")
        if packager and packager != "(none)":
            component["supplier"] = {"name": packager}

        # Add properties for RPM metadata
        properties = []

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

        # Add GPG signature information if available
        signature = self.rpm_helper.get_rpm_signature(rpm_path)
        if signature:
            # Parse signature info
            sig_props = self.parse_signature_to_properties(signature)
            properties.extend(sig_props)

        if properties:
            component["properties"] = properties

        return component

    def parse_signature_to_properties(self, signature_string):
        """Parses RPM signature string into CycloneDX properties."""
        properties = []
        if not signature_string or signature_string == "(none)":
            return properties

        properties.append({"name": "mock:signature:type", "value": "GPG"})

        if "RSA/SHA256" in signature_string:
            properties.append({"name": "mock:signature:algorithm", "value": "RSA/SHA256"})
        elif "DSA/SHA1" in signature_string:
            properties.append({"name": "mock:signature:algorithm", "value": "DSA/SHA1"})
        elif "ECDSA/SHA256" in signature_string:
            properties.append({"name": "mock:signature:algorithm", "value": "ECDSA/SHA256"})
        elif "Ed25519/SHA256" in signature_string:
            properties.append({"name": "mock:signature:algorithm", "value": "Ed25519/SHA256"})

        key_id_match = re.search(r'Key ID ([0-9a-fA-F]+)', signature_string)
        if key_id_match:
            properties.append({"name": "mock:signature:key", "value": key_id_match.group(1)})

        date_match = re.search(
            r'([A-Za-z]{3} [A-Za-z]{3}\s+\d{1,2} \d{2}:\d{2}:\d{2} \d{4})', signature_string
        )
        if date_match:
            properties.append({"name": "mock:signature:date", "value": date_match.group(1)})

        properties.append({"name": "mock:signature:raw", "value": signature_string})
        return properties

    def signature_info_to_properties(self, signature_info):
        """Converts signature info dict to CycloneDX properties."""
        properties = []
        sig_type = signature_info.get("signature_type", "unsigned")
        properties.append({"name": "mock:signature:type", "value": sig_type})

        if (
            sig_type not in ('unsigned', 'unknown') and
            'missing key' not in sig_type and
            'BAD' not in sig_type
        ):
            algorithm = signature_info.get("signature_algorithm")
            if algorithm:
                properties.append({"name": "mock:signature:algorithm", "value": algorithm})

            key_id = signature_info.get("signature_key")
            if key_id:
                properties.append({"name": "mock:signature:key", "value": key_id})

            sig_date = signature_info.get("signature_date")
            if sig_date:
                properties.append({"name": "mock:signature:date", "value": sig_date})

            sig_valid = signature_info.get("signature_valid", False)
            properties.append({"name": "mock:signature:valid", "value": str(sig_valid).lower()})

            raw_data = signature_info.get("raw_signature_data")
            if raw_data:
                properties.append({"name": "mock:signature:raw", "value": raw_data})

        return properties

    def create_cyclonedx_document(self):
        """Initializes the base CycloneDX JSON structure."""
        return {
            "bomFormat": "CycloneDX",
            "specVersion": "1.5",
            "serialNumber": f"urn:uuid:{uuid.uuid4()}",
            "version": 1,
            "metadata": {},
            "components": [],
            "dependencies": []
        }

    def generate_bom_ref(self, package_name, version, _component_type="package"):
        """Generates a stable bom-ref ID based on package name and version."""
        safe_name = re.sub(r'[^a-zA-Z0-9.-]', '-', package_name)
        safe_version = re.sub(r'[^a-zA-Z0-9.-]', '-', version)
        return f"build-output:{safe_name}-{safe_version}"

    def generate_file_bom_ref(self, package_name, package_version, file_path):
        """Generates a unique but stable bom-ref for a file."""
        safe_name = re.sub(r'[^a-zA-Z0-9.-]', '-', package_name)
        safe_version = re.sub(r'[^a-zA-Z0-9.-]', '-', package_version)
        safe_path = re.sub(r'[^a-zA-Z0-9.-]', '-', file_path.lstrip('/'))
        return f"file:{safe_name}-{safe_version}:{safe_path}"

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

        safe_name = re.sub(r'[^a-zA-Z0-9.-]', '-', filename)
        hash_suffix = sha256[:8] if sha256 else "unknown"
        bom_ref = f"source-file:{safe_name}-{hash_suffix}"

        comp = {
            "type": "file",
            "bom-ref": bom_ref,
            "name": filename,
            "properties": [
                {"name": "mock:source:type", "value": "patch" if self.is_patch_file(filename) else "archive"}
            ]
        }
        if sha256:
            comp["hashes"] = [{"alg": "SHA-256", "content": sha256}]
        if sig:
            comp["properties"].append({"name": "mock:signature:status", "value": sig})

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

    def append_source_properties(self, properties, source_entries):
        """Appends source and patch references to a component's properties."""
        for i, src in enumerate(source_entries):
            filename = src["filename"]
            prop_name = f"mock:source:patch{i}" if self.is_patch_file(filename) else f"mock:source:file{i}"
            properties.append({
                "name": prop_name,
                "value": src["bom-ref"]
            })

    def get_source_file_bom_refs(self, _package_name, source_files):
        """Returns a list of bom-refs for source files."""
        refs = []
        for src in source_files:
            filename = src["filename"]
            sha256 = src.get("sha256")
            safe_name = re.sub(r'[^a-zA-Z0-9.-]', '-', filename)
            hash_suffix = sha256[:8] if sha256 else "unknown"
            bom_ref = f"source-file:{safe_name}-{hash_suffix}"
            refs.append(bom_ref)
        return refs

    def get_iso_timestamp(self):
        """Returns the current UTC time in ISO 8601 format."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def create_dependency(self, bom_ref, dependencies, component_map, distro_obj):
        """Creates a dependency entry mapping raw requires to parsed bom-refs."""
        dep_entry = {
            "ref": bom_ref,
            "dependsOn": []
        }
        for raw_dep in dependencies:
            target_ref = self.dependency_to_bom_ref(raw_dep, component_map, distro_obj)
            if target_ref and target_ref not in dep_entry["dependsOn"] and target_ref != bom_ref:
                dep_entry["dependsOn"].append(target_ref)
        
        return dep_entry if dep_entry["dependsOn"] else None

    def dependency_to_bom_ref(self, dependency_string, component_map, _distro):
        """
        Attempts to map a raw RPM dependency string (e.g., 'libc.so.6', 'bash >= 4.0')
        to a concrete bom-ref in the component_map.
        """
        if not dependency_string:
            return None

        clean_dep = dependency_string.strip()
        
        if " " in clean_dep:
            # Handle forms like 'bash >= 5.0' -> just look for 'bash'
            pkg_name = clean_dep.split()[0].strip()
            # If the requirement is a package name we know about
            if pkg_name in component_map:
                return component_map[pkg_name]

            # Sometimes dependencies look like 'config(bash) = 5.0'
            if clean_dep.startswith("config(") and ")" in clean_dep:
                inner_name = clean_dep[7:clean_dep.find(")")]
                if inner_name in component_map:
                    return component_map[inner_name]

        else:
            # Handle raw names like 'bash' or 'libc.so.6'
            if clean_dep in component_map:
                return component_map[clean_dep]

            # Check if any component *provides* this string (this is an approximation, 
            # true resolution requires full RPM capability mapping which is slow)
            # For now, we rely on the direct package name match which covers 80% of cases.

        return None
    def process_built_packages(self, bom, rpm_files, build_dir, distro_id,
                               source_component_entries, build_subject_name,
                               build_toolchain_packages, toolchain_bom_refs):
        """Processes binary RPMs and creates structured CycloneDX components and dependencies."""
        built_package_bom_refs = []
        all_built_components = []
        component_map = {}
        primary_rpm_metadata = None

        # Build component map from toolchain packages
        for toolchain_pkg in build_toolchain_packages:
            pkg_name = toolchain_pkg.get("name")
            pkg_version = toolchain_pkg.get("version")
            if pkg_name and pkg_version:
                purl = self.rpm_helper.generate_purl(pkg_name, pkg_version, distro_id)
                component_map[pkg_name.lower()] = purl

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
                if package_name:
                    component_map[package_name.lower()] = bom_ref

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
                    self.buildroot.root_log.debug(f"[SBOM] Selecting {package_name} as primary metadata source")
                    primary_rpm_metadata = self.rpm_helper.get_rpm_metadata(rpm_path)

            # File components
            if package_name and package_version and self.include_file_components:
                # Extract CPE and GPG info from the component to pass to files
                rpm_cpe = None
                for ext_ref in component.get("externalReferences", []):
                    if ext_ref.get("comment") == "CPE 2.3":
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
                        # Set scope to required for all files in the produced RPM
                        file_comp["scope"] = "required"
                        component["components"].append(file_comp)
                        
                        if self.should_include_file_dependency(file_comp.get("name", "")):
                            bom["dependencies"].append({
                                "ref": file_comp["bom-ref"],
                                "dependsOn": [bom_ref]
                            })
                    
                    # Sort file components alphabetically
                    component["components"].sort(key=lambda x: x.get("name", ""))

            # Dependencies
            dependencies = self.rpm_helper.get_rpm_dependencies(rpm_path) or []
            runtime_dependency = self.create_dependency(
                bom_ref, dependencies, component_map, distro_id
            )

            all_depends_on = []
            if runtime_dependency and runtime_dependency.get("dependsOn"):
                all_depends_on.extend(runtime_dependency.get("dependsOn"))

            if self.include_toolchain_dependencies and toolchain_bom_refs:
                for t_ref in toolchain_bom_refs:
                    if t_ref not in all_depends_on:
                        all_depends_on.append(t_ref)

            all_depends_on = sorted(list(set(all_depends_on)))
            if all_depends_on:
                bom["dependencies"].append({"ref": bom_ref, "dependsOn": all_depends_on})
            elif runtime_dependency:
                bom["dependencies"].append(runtime_dependency)
                
            all_built_components.append(component)

        return built_package_bom_refs, primary_rpm_metadata, all_built_components

    # pylint: disable=too-many-arguments,too-many-locals,too-many-branches,too-many-statements,too-many-positional-arguments

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
            if vendor and vendor != "(none)":
                bom["metadata"]["manufacturer"] = {"name": vendor}
                bom["metadata"]["authors"] = [{"name": vendor}]

            packager = primary_rpm_metadata.get("packager")
            if packager and packager != "(none)":
                bom["metadata"]["supplier"] = {"name": packager}

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
                                build_toolchain_packages, distro_id,
                                built_package_bom_refs, toolchain_bom_refs,
                                spec_metadata=None,
                                source_components=None,
                                toolchain_components=None,
                                all_built_components=None):
        """Finalizes BOM dependencies, linking primary package to hierarchical grouping components
        and implementing nested component composition."""
        # Find primary component ref (metadata.component or first built package)
        primary_ref = None
        if bom.get("metadata") and bom["metadata"].get("component"):
            primary_ref = bom["metadata"]["component"].get("bom-ref")
        
        if not primary_ref:
            return

        # Create virtual grouping references
        inputs_ref = "build:inputs"
        toolchain_ref = "build:toolchain"
        outputs_ref = "build:outputs"

        # Prepare grouping components
        inputs_group = {
            "type": "application",
            "bom-ref": inputs_ref,
            "name": "Build Inputs",
            "description": "Source code and patches used for the build",
            "properties": [{"name": "mock:type", "value": "grouping-node"}]
        }
        if source_components:
            inputs_group["components"] = sorted(source_components, key=lambda x: x.get("name", ""))

        toolchain_group = {
            "type": "application",
            "bom-ref": toolchain_ref,
            "name": "Build Toolchain",
            "description": "Packages and tools used to perform the build",
            "scope": "excluded", # Tools are not part of the runtime payload
            "properties": [{"name": "mock:type", "value": "grouping-node"}]
        }
        if toolchain_components:
            # Group toolchain components by their GPG Key ID
            signer_groups = {}
            pkg_map = {p.get("name"): p for p in build_toolchain_packages}
            
            for comp in toolchain_components:
                comp["scope"] = "excluded"
                pkg_info = pkg_map.get(comp.get("name"))
                sig_info = pkg_info.get("digital_signature", {}) if pkg_info else {}
                key_id = sig_info.get("signature_key", "unsigned")
                
                # Attach signature properties to the individual package component
                if sig_info:
                    sig_props = self.signature_info_to_properties(sig_info)
                    comp["properties"] = comp.get("properties", [])
                    comp["properties"].extend([p for p in sig_props if p["name"] != "mock:signature:raw"])

                if key_id not in signer_groups:
                    # Create group properties - common only to the signer
                    group_props = [
                        {"name": "mock:role", "value": "build-toolchain"},
                        {"name": "mock:type", "value": "signer-group"},
                        {"name": "mock:signature:key", "value": key_id}
                    ]
                    
                    signer_groups[key_id] = {
                        "type": "application",
                        "bom-ref": f"signer:{key_id}",
                        "name": f"Packages signed by {key_id}" if key_id != "unsigned" else "Unsigned Packages",
                        "scope": "excluded",
                        "properties": group_props,
                        "components": []
                    }
                signer_groups[key_id]["components"].append(comp)
            
            # Add signer groups as children of toolchain_group
            sorted_groups = sorted(
                list(signer_groups.values()), 
                key=lambda x: x.get("name", "")
            )
            for group in sorted_groups:
                group["components"].sort(key=lambda x: x.get("name", ""))
            
            toolchain_group["components"] = sorted_groups

        outputs_group = {
            "type": "application",
            "bom-ref": outputs_ref,
            "name": "RPM Contents",
            "description": "RPM packages and their contained files produced by the build",
            "scope": "required",
            "properties": [{"name": "mock:type", "value": "grouping-node"}]
        }
        if all_built_components:
            outputs_group["components"] = sorted(all_built_components, key=lambda x: x.get("name", ""))

        # Nest groups into the primary component
        primary_comp = bom["metadata"]["component"]
        primary_comp["components"] = [inputs_group, toolchain_group, outputs_group]
        # Sort metadata components alphabetically
        primary_comp["components"].sort(key=lambda x: x.get("name", ""))

        # 1. Primary component depends on the three groups
        bom["dependencies"].append({
            "ref": primary_ref,
            "dependsOn": sorted([inputs_ref, toolchain_ref, outputs_ref])
        })

        # 2. Build Inputs Group -> Source components
        input_deps = []
        for entry in source_component_entries:
            if entry.get("bom-ref"):
                input_deps.append(entry["bom-ref"])
        
        if input_deps:
            bom["dependencies"].append({
                "ref": inputs_ref,
                "dependsOn": sorted(list(set(input_deps)))
            })

        # 3. Build Toolchain Group -> Signer Groups
        signer_refs = [g["bom-ref"] for g in toolchain_group.get("components", [])]
        if signer_refs:
            bom["dependencies"].append({
                "ref": toolchain_ref,
                "dependsOn": sorted(signer_refs)
            })
            
            # 3b. Signer Groups -> Individual packages
            for group in toolchain_group["components"]:
                pkg_refs = [c["bom-ref"] for c in group["components"]]
                bom["dependencies"].append({
                    "ref": group["bom-ref"],
                    "dependsOn": sorted(pkg_refs)
                })

        # 4. RPM Contents Group -> Built RPMs (Packages)
        if built_package_bom_refs:
            bom["dependencies"].append({
                "ref": outputs_ref,
                "dependsOn": sorted(list(set(built_package_bom_refs)))
            })



    def create_toolchain_component(self, toolchain_pkg, distro_obj):
        """Creates a CycloneDX component for a build toolchain package."""
        package_name = toolchain_pkg.get("name")
        version = toolchain_pkg.get("version")

        if not package_name or not version:
            return None

        # Generate PURL and bom-ref
        purl = self.rpm_helper.generate_purl(package_name, version, distro_obj, arch=toolchain_pkg.get("arch"))
        bom_ref = purl

        component = {
            "type": "library",
            "bom-ref": bom_ref,
            "name": package_name,
            "version": version,
            "purl": purl
        }

        # Add checksum - REMOVED per user request to only have hashes for files contained in RPM
        # (This follows the rule that only the 'RPM Contents' section should have hashes)
        # checksum = toolchain_pkg.get("checksum")
        # if checksum and checksum != "error" and not checksum.startswith("error"):
        #     if len(checksum) == 64:
        #         alg = "SHA-256"
        #     elif len(checksum) == 40:
        #         alg = "SHA-1"
        #     else:
        #         alg = "SHA-256"
        #     component["hashes"] = [{"alg": alg, "content": checksum}]

        # Add CPE
        cpe = toolchain_pkg.get("cpe")
        if cpe:
            component["externalReferences"] = [
                {
                    "type": "other",
                    "comment": "CPE 2.3",
                    "url": cpe
                }
            ]

        # Add license
        license_str = toolchain_pkg.get("licenseDeclared")
        if license_str and license_str != "(none)":
            component["licenses"] = [
                {
                    "expression": license_str
                }
            ]

        # Add properties
        properties = []

        # Add build date if available
        signature_info = toolchain_pkg.get("digital_signature", {})
        build_date = signature_info.get("build_date")
        if build_date:
            properties.append({
                "name": "mock:build:date",
                "value": build_date
            })

        if properties:
            component["properties"] = properties

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

            # Filtering logic
            if not self.include_debug_files and ("/usr/lib/debug/" in file_path or "/usr/src/debug/" in file_path):
                self.buildroot.root_log.debug(f"[SBOM] Filtering debug file: {file_path}")
                continue
            
            if not self.include_man_pages and ("/usr/share/man/" in file_path):
                self.buildroot.root_log.debug(f"[SBOM] Filtering man page: {file_path}")
                continue

            # Filter files based on configuration
            if not self.include_debug_files:
                if '/usr/lib/debug/' in file_path or file_path.endswith('.debug'):
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

            # Add hash if available with detected algorithm
            if file_hash:
                # Map RPM algo ID to CycloneDX algo name
                # 8: SHA-256, 10: SHA-512, 1: MD5, 2: SHA-1
                algo_map = {
                    8: "SHA-256",
                    10: "SHA-512",
                    1: "MD5",
                    2: "SHA-1",
                    9: "SHA-384",
                    11: "SHA-224"
                }
                alg_name = algo_map.get(algo_id, "SHA-256")
                
                component["hashes"] = [
                    {
                        "alg": alg_name,
                        "content": file_hash
                    }
                ]

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


    def should_include_file_dependency(self, file_path):
        """Determine if a file should have a dependency entry."""
        if not self.include_file_dependencies:
            return False

        # Filter out debug files if configured
        if not self.include_debug_files:
            if '/usr/lib/debug/' in file_path or file_path.endswith('.debug'):
                return False

        # Filter out man pages if configured
        if not self.include_man_pages:
            if (
                '/usr/share/man/' in file_path or
                (file_path.endswith('.gz') and '/man' in file_path)
            ):
                return False

        return True

