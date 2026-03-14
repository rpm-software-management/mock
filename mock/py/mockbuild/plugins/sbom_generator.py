# -*- coding: utf-8 -*-
# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# License: GPL2 or later see COPYING
# Written by Scott R. Shinn <scott@atomicorp.com>
# Copyright (C) 2026, Atomicorp, Inc.
"""Mock plugin for generating CycloneDX SBOMs from built RPM packages."""

import os
import json
import subprocess
import hashlib
import re
import socket
import uuid
import tempfile
import shlex
import traceback
from datetime import datetime, timezone

import distro
import rpm  # pylint: disable=no-member



import mockbuild.file_util
from mockbuild.trace_decorator import traceLog

# pylint: disable=invalid-name
requires_api_version = "1.1"  # Ensure compatibility with mock API
# pylint: enable=invalid-name

# Plugin entry point
@traceLog()
def init(plugins, conf, buildroot):
    """Initializes the SBOM generator plugin."""
    # Ensure configuration exists for the plugin
    if "sbom_generator_opts" not in conf:
        conf["sbom_generator_opts"] = {}

    # Check for valid SBOM type configuration
    opts = conf["sbom_generator_opts"]
    if "type" in opts and opts["type"] not in ("cyclonedx", "spdx"):
        # We only support cyclonedx and spdx for now
        buildroot.root_log.warning(
            f"SBOM generator type '{opts['type']}' not supported, defaulting to 'cyclonedx'"
        )
        opts["type"] = "cyclonedx"

    SBOMGenerator(plugins, conf["sbom_generator_opts"], buildroot)

class SBOMGenerator:
    """Generates SBOM for the built packages."""
    # pylint: disable=too-few-public-methods,too-many-instance-attributes
    @traceLog()
    def __init__(self, plugins, conf, buildroot):

        self.buildroot = buildroot
        self.state = buildroot.state
        self.rootdir = buildroot.rootdir
        self.builddir = buildroot.builddir
        self.conf = conf
        self.sbom_enabled = self.conf.get('generate_sbom', True)
        self.sbom_type = self.conf.get('type', 'cyclonedx')
        self.sbom_done = False

        # Configuration options for file-level dependencies and filtering
        self.include_file_dependencies = self.conf.get('include_file_dependencies', False)
        self.include_file_components = self.conf.get('include_file_components', True)
        self.include_debug_files = self.conf.get('include_debug_files', False)
        self.include_man_pages = self.conf.get('include_man_pages', True)
        self.include_source_dependencies = self.conf.get('include_source_dependencies', True)
        self.include_toolchain_dependencies = self.conf.get('include_toolchain_dependencies', False)

        self.prebuild_source_files = []
        self.prebuild_spec_metadata = {}

        plugins.add_hook("prebuild", self._capture_prebuild_state)
        plugins.add_hook("postbuild", self._generate_sbom_post_build_hook)

    @traceLog()
    def _capture_prebuild_state(self):
        """Captures pristine source artifacts before the build begins."""

        self.buildroot.root_log.debug("Capturing pre-build state from SPECS and SOURCES")
        
        # Look for spec file in the build directory
        specs_dir = os.path.join(self.buildroot.rootdir, "builddir/build/SPECS")
        try:
            if os.path.exists(specs_dir):
                for file in os.listdir(specs_dir):
                    if file.endswith('.spec'):
                        spec_file = os.path.join(specs_dir, file)
                        self.buildroot.root_log.debug(f"Parsing spec file for pre-build state: {spec_file}")
                        metadata, sources = self.parse_spec_file(spec_file)
                        self.prebuild_spec_metadata = metadata
                        self.prebuild_source_files = sources
                        break
            else:
                self.buildroot.root_log.debug("SPECS directory does not exist for pre-build capture.")
        except Exception as e:
            self.buildroot.root_log.debug(f"Failed to capture pre-build state: {e}")

    def _create_cyclonedx_document(self):
        """Creates the base CycloneDX document structure."""
        return {
            "bomFormat": "CycloneDX",
            "specVersion": "1.5",
            "serialNumber": f"urn:uuid:{uuid.uuid4()}",
            "version": 1,
            "metadata": self._create_metadata(),
            "components": [],
            "dependencies": []
        }

    def _create_metadata(self):
        """Creates CycloneDX metadata object with Mock-specific build information."""
        metadata = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
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

        # Add Mock-specific build metadata as properties
        properties = metadata["properties"]

        # Add SBOM completeness declaration
        properties.append({
            "name": "sbom:completeness",
            "value": "complete"
        })

        properties.append({
            "name": "mock:build:host",
            "value": socket.gethostname()
        })

        distro_name = self.get_distribution()
        if distro_name:
            properties.append({
                "name": "mock:build:distribution",
                "value": distro_name
            })

        # Add chroot information if available
        if hasattr(self.buildroot, 'rootdir') and self.buildroot.rootdir:
            properties.append({
                "name": "mock:build:chroot",
                "value": self.buildroot.rootdir
            })

        # Add Mock config if available
        if hasattr(self.buildroot, 'config') and self.buildroot.config:
            config = self.buildroot.config
            config_name = config.get('config_path', 'unknown')
            properties.append({
                "name": "mock:build:config",
                "value": config_name
            })

            # Capture network isolation and access status
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

        hardening_props = self._collect_build_hardening_properties()
        if hardening_props:
            properties.extend(hardening_props)

        return metadata

    def _evaluate_rpm_macro(self, macro):
        """Evaluate an RPM macro inside the buildroot (falling back to host)."""
        cmd = ["rpm", "--eval", macro]
        # Prefer evaluating inside the chroot to capture build-specific settings
        if hasattr(self.buildroot, "doChroot"):
            try:
                output, _ = self.buildroot.doChroot(
                    cmd,
                    shell=False,
                    returnOutput=True,
                    printOutput=False,
                )
                if output:
                    return output.strip()
            except Exception as exc:  # pylint: disable=broad-except
                self.buildroot.root_log.debug(
                    f"Warning: failed to eval macro {macro} in chroot: {exc}"
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
            self.buildroot.root_log.debug(f"Warning: failed to eval macro {macro}: {exc}")
            return ""

    def _read_file_from_chroot(self, relative_path):
        """
        Read a file from inside the buildroot.
        Returns the file content as a string or empty string on failure.
        """
        chroot_path = os.path.join(self.buildroot.rootdir, relative_path.lstrip("/"))
        try:
            with open(chroot_path, "r", encoding="utf-8", errors="ignore") as handle:
                return handle.read().strip()
        except (OSError, IOError):
            pass
        if hasattr(self.buildroot, "doChroot"):
            try:
                output, _ = self.buildroot.doChroot(
                    ["cat", relative_path],
                    shell=False,
                    returnOutput=True,
                    printOutput=False,
                )
                return output.strip()
            except Exception:  # pylint: disable=broad-except
                return ""
        return ""

    def _collect_build_hardening_properties(self):
        """
        Capture key compiler/linker macro settings that influence hardening
        (FORTIFY, PIE, RELRO, LTO, etc.) and expose them as SBOM properties.
        """
        macro_queries = {
            "build:hardening:optflags": "%{?optflags}",
            "build:hardening:hardening_cflags": "%{?_hardening_cflags}",
            "build:hardening:global_cflags": "%{?__global_cflags}",
            "build:hardening:global_ldflags": "%{?__global_ldflags}",
            "build:hardening:build_ldflags": "%{?build_ldflags}",
        }

        properties = []
        macro_values = {}
        for prop_name, macro in macro_queries.items():
            value = self._evaluate_rpm_macro(macro)
            macro_values[prop_name] = value
            if value:
                properties.append({
                    "name": prop_name,
                    "value": value
                })

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

        def _contains_flag(flag):
            return flag in flag_union if flag_union else False

        feature_map = {
            "build:hardening:fortify_enabled": any(
                token in flag_union
                for token in ["-d_fortify_source", "_fortify_source="]
            ),
            "build:hardening:pie_enabled": any(
                token in flag_union for token in ["-fpie", "-pie"]
            ),
            "build:hardening:relro_enabled": any(
                token in flag_union
                for token in ["-z relro", "-z now", "-wl,-z,relro", "-wl,-z,now"]
            ),
            "build:hardening:lto_enabled": _contains_flag("-flto"),
        }
        for name, enabled in feature_map.items():
            properties.append({
                "name": name,
                "value": "true" if enabled else "false"
            })

        fips_value = self._read_file_from_chroot("/proc/sys/crypto/fips_enabled")
        if fips_value != "":
            properties.append({
                "name": "build:hardening:fips_enabled",
                "value": "true" if fips_value.strip() == "1" else "false"
            })

        return properties

    def _generate_purl(self, package_name, version, distro_obj=None, arch=None):
        """Generate Package URL (PURL) for RPM package."""
        if not distro_obj:
            distro_obj = self.detect_chroot_distribution() or "fedora"

        # Clean package name for PURL (lowercase, no special chars)
        clean_name = re.sub(r'[^a-zA-Z0-9._-]', '-', package_name.lower())

        purl = f"pkg:rpm/{distro_obj}/{clean_name}@{version}"
        if arch:
            purl += f"?arch={arch}"
        return purl

    def _generate_bom_ref(self, package_name, version, _component_type="package"):
        """Generate a unique bom-ref identifier for a component."""
        # Use PURL as bom-ref for consistency
        distro_obj = self.detect_chroot_distribution() or "fedora"
        return self._generate_purl(package_name, version, distro_obj)

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
            self.buildroot.root_log.debug(f"Failed to scan build directory {build_dir}: {e}")

        # Look for spec file in the chroot build directory
        build_build_dir = os.path.join(self.buildroot.rootdir, "builddir/build")
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
                self.buildroot.root_log.debug(
                    f"Failed to scan chroot build dir {build_build_dir}: {e}"
                )

        return rpm_files, src_rpm_files, spec_file

    def _get_build_subject_metadata(self, spec_file, src_rpm_files, build_dir):
        """Determines the build subject metadata (name, version, release)."""
        build_subject_name = None
        build_subject_version = None
        build_subject_release = None
        source_files = []
        spec_metadata = {}

        if hasattr(self, 'prebuild_spec_metadata') and self.prebuild_spec_metadata:
            spec_metadata = self.prebuild_spec_metadata
            source_files = self.prebuild_source_files
            build_subject_name = spec_metadata.get("name")
            build_subject_version = spec_metadata.get("version")
            build_subject_release = spec_metadata.get("release")
        elif spec_file:
            spec_metadata, parsed_sources = self.parse_spec_file(spec_file)
            if spec_metadata:
                build_subject_name = spec_metadata.get("name")
                build_subject_version = spec_metadata.get("version")
                build_subject_release = spec_metadata.get("release")
            if parsed_sources:
                source_files = parsed_sources

        if src_rpm_files:
            srpm_path = os.path.join(build_dir, src_rpm_files[0])
            srpm_metadata = self.get_rpm_metadata(srpm_path)
            if srpm_metadata:
                if not build_subject_name:
                    build_subject_name = srpm_metadata.get("name")
                if not build_subject_version:
                    build_subject_version = srpm_metadata.get("version")
                if not build_subject_release:
                    build_subject_release = srpm_metadata.get("release")

            if not source_files:
                # Extract metadata for source files from source RPM without full extraction
                source_files = self.extract_source_files_from_srpm(srpm_path)

            # Record the source RPM itself as an input artifact
            srpm_name = src_rpm_files[0]
            srpm_sig = self.get_rpm_signature(srpm_path)
            # Add to the beginning of the list for visibility
            source_files.insert(0, {
                "filename": srpm_name,
                "digital_signature": srpm_sig,
                "source_type": "source_rpm"
            })

        return (
            spec_metadata, build_subject_name, build_subject_version,
            build_subject_release, source_files
        )

    def _add_source_components(self, _bom, source_files):
        """Converts source files to CycloneDX components and returns components and metadata entries."""
        source_components = []
        source_component_entries = []
        for source_file in source_files:
            component = self._create_source_file_component(source_file)
            if component:
                source_components.append(component)
                filename = source_file.get("filename")
                source_component_entries.append({
                    "filename": filename,
                    "bom-ref": component.get("bom-ref"),
                    "type": "patch" if self._is_patch_file(filename) else "source"
                })
        return source_components, source_component_entries

    def _add_toolchain_components(self, _bom, build_toolchain_packages, distro_id):
        """Adds toolchain components to the BOM and returns their components and bom-refs."""
        toolchain_components = []
        toolchain_bom_refs = []
        for toolchain_pkg in build_toolchain_packages:
            component = self._create_toolchain_component(toolchain_pkg, distro_id)
            if component:
                bom_ref = component.get("bom-ref")
                if bom_ref:
                    toolchain_bom_refs.append(bom_ref)
                toolchain_components.append(component)
        return toolchain_components, toolchain_bom_refs

    @traceLog()
    # pylint: disable=too-many-locals
    def _generate_sbom_post_build_hook(self):
        """Plugin hook called after the build is complete."""
        if self.sbom_done or not self.sbom_enabled:
            return

        state_text = f"Generating {self.sbom_type.upper()} SBOM for built packages v1.0"
        self.state.start(state_text)

        try:
            build_dir = self.buildroot.resultdir
            rpm_files, src_rpm_files, spec_file = self._find_build_artifacts(build_dir)

            if not rpm_files and not src_rpm_files and not spec_file:
                self.buildroot.root_log.debug(
                    "No RPM, source RPM, or spec file found for SBOM generation."
                )
                return

            # Get build subject metadata
            (
                spec_metadata, build_subject_name, build_subject_version,
                build_subject_release, source_files
            ) = self._get_build_subject_metadata(spec_file, src_rpm_files, build_dir)

            if not build_subject_name or not build_subject_version or not build_subject_release:
                self.buildroot.root_log.debug("Cannot generate SBOM - build metadata incomplete")
                return

            # Gather common data
            distro_id = self.detect_chroot_distribution() or "fedora"
            build_toolchain_packages = self.get_build_toolchain_packages()

            # Dispatch based on type
            if self.sbom_type == "spdx":
                sbom_filename = (
                    f"{build_subject_name}-{build_subject_version}-{build_subject_release}.spdx.json"
                )
                out_file = os.path.join(self.buildroot.resultdir, sbom_filename)

                doc = self._generate_spdx_document(
                    build_subject_name, build_subject_version, build_subject_release,
                    build_dir, rpm_files, source_files,
                    build_toolchain_packages, distro_id, spec_metadata=spec_metadata
                )

                with open(out_file, "w", encoding="utf-8") as f:
                    json.dump(doc, f, indent=2)

                self.buildroot.root_log.debug(f"SPDX SBOM successfully written to: {out_file}")

            else:
                # Default: CycloneDX
                sbom_filename = (
                    f"{build_subject_name}-{build_subject_version}-{build_subject_release}.sbom"
                )
                out_file = os.path.join(self.buildroot.resultdir, sbom_filename)

                # Create CycloneDX document
                bom = self._create_cyclonedx_document()

                # Add source and toolchain components
                source_components, source_component_entries = self._add_source_components(bom, source_files)
                toolchain_components, toolchain_bom_refs = self._add_toolchain_components(
                    bom, build_toolchain_packages, distro_id
                )

                # Process binary RPMs and convert to components
                (
                    built_package_bom_refs, primary_rpm_metadata, all_built_components
                ) = self._process_built_packages(
                    bom, rpm_files + src_rpm_files, build_dir, distro_id, source_component_entries,
                    build_subject_name, build_toolchain_packages, toolchain_bom_refs
                )

                # Add RPM-specific metadata and finalize dependencies
                self._finalize_bom_metadata(bom, primary_rpm_metadata, built_package_bom_refs,
                                            build_subject_name, build_subject_version,
                                            build_subject_release, distro_id,
                                            spec_metadata=spec_metadata)
                self._finalize_dependencies(bom, source_component_entries,
                                            build_toolchain_packages, distro_id,
                                            built_package_bom_refs, toolchain_bom_refs,
                                            spec_metadata=spec_metadata,
                                            source_components=source_components,
                                            toolchain_components=toolchain_components,
                                            all_built_components=all_built_components)

                # Write CycloneDX BOM
                with open(out_file, "w", encoding="utf-8") as f:
                    json.dump(bom, f, indent=2)

                self.buildroot.root_log.debug(f"CycloneDX SBOM successfully written to: {out_file}")

        # pylint: disable=broad-exception-caught
        except Exception as e:
            self.buildroot.root_log.debug(f"An error occurred during SBOM generation: {e}")
            traceback.print_exc()
        finally:
            self.sbom_done = True
            self.state.finish(state_text)

    # pylint: disable=too-many-arguments,too-many-locals,too-many-branches,too-many-statements,too-many-positional-arguments
    def _process_built_packages(self, bom, rpm_files, build_dir, distro_id,
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
                purl = self._generate_purl(pkg_name, pkg_version, distro_id)
                component_map[pkg_name.lower()] = purl

        for rpm_file in rpm_files:
            rpm_path = os.path.join(build_dir, rpm_file)
            component = self._create_built_package_component(
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
                    primary_rpm_metadata = self.get_rpm_metadata(rpm_path)
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
                    primary_rpm_metadata = self.get_rpm_metadata(rpm_path)

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

                file_components = self._create_file_components(
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
                        
                        if self._should_include_file_dependency(file_comp.get("name", "")):
                            bom["dependencies"].append({
                                "ref": file_comp["bom-ref"],
                                "dependsOn": [bom_ref]
                            })
                    
                    # Sort file components alphabetically
                    component["components"].sort(key=lambda x: x.get("name", ""))

            # Dependencies
            dependencies = self.get_rpm_dependencies(rpm_path)
            runtime_dependency = self._create_dependency(
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
    def _finalize_bom_metadata(self, bom, primary_rpm_metadata, built_package_bom_refs,
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
                        component_obj["purl"] = self._generate_purl(
                            aggregate_name, aggregate_version, distro_id
                        )
                    bom["metadata"]["component"] = component_obj

    # pylint: disable=too-many-locals,too-many-branches,too-many-statements
    def _finalize_dependencies(self, bom, source_component_entries,
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
                    sig_props = self._signature_info_to_properties(sig_info)
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


    def _create_built_package_component(
        self, rpm_path, distro_obj, _source_components=None
    ):
        """Creates a CycloneDX component for a built RPM package."""
        package_data = self.get_rpm_metadata(rpm_path)
        if not package_data:
            return None

        package_name = package_data.get("name")
        version = package_data.get("version")
        release = package_data.get("release")
        arch = package_data.get("arch")

        # Combine version and release
        full_version = f"{version}-{release}" if release else version

        # Generate PURL and bom-ref
        purl = self._generate_purl(package_name, full_version, distro_obj, arch)
        bom_ref = purl

        # Determine component type (application vs library)
        # Most RPMs are libraries, but we could check for executables
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
        cpe = self.generate_cpe(package_name, version, vendor=vendor)
        if cpe:
            component["externalReferences"] = [
                {
                    "type": "other",
                    "comment": "CPE 2.3",
                    "url": cpe
                }
            ]

        # Add hierarchical grouping for "RPM Contents"
        outputs_ref = "build:outputs" # This will be the "RPM Contents" group

        # Add hash of RPM file - REMOVED per user request to only have hashes for files contained in RPM
        # or if needed for PURL integrity, but we'll prioritize the "only" constraint.
        # rpm_hash = package_data.get("sha256")
        # if not rpm_hash or rpm_hash == "(none)":
        #     rpm_hash = self.hash_file(rpm_path)
        
        # if rpm_hash:
        #     component["hashes"] = [
        #         {
        #             "alg": "SHA-256",
        #             "content": rpm_hash
        #         }
        #     ]

        # Add license information
        license_str = package_data.get("license")
        if license_str and license_str != "(none)":
            component["licenses"] = [
                {
                    "expression": license_str
                }
            ]

        # Add supplier information (from Packager field)
        packager = package_data.get("packager")
        if packager and packager != "(none)":
            component["supplier"] = {
                "name": packager
            }

        # Add properties for RPM metadata
        properties = []

        properties.append({
            "name": "mock:rpm:filename",
            "value": os.path.basename(rpm_path)
        })

        vendor = package_data.get("vendor")
        if vendor and vendor != "(none)":
            properties.append({
                "name": "mock:rpm:vendor",
                "value": vendor
            })

        packager = package_data.get("packager")
        if packager and packager != "(none)":
            properties.append({
                "name": "mock:rpm:packager",
                "value": packager
            })

        buildhost = package_data.get("buildhost")
        if buildhost and buildhost != "(none)":
            properties.append({
                "name": "mock:rpm:buildhost",
                "value": buildhost
            })

        buildtime_iso = self._format_epoch_timestamp(package_data.get("buildtime"))
        if buildtime_iso:
            properties.append({
                "name": "mock:rpm:buildtime",
                "value": buildtime_iso
            })

        group = package_data.get("group")
        if group and group != "(none)":
            properties.append({
                "name": "mock:rpm:group",
                "value": group
            })

        epoch_val = package_data.get("epoch")
        if epoch_val and epoch_val != "(none)":
            properties.append({
                "name": "mock:rpm:epoch",
                "value": epoch_val
            })

        distribution = package_data.get("distribution")
        if distribution and distribution != "(none)":
            properties.append({
                "name": "mock:rpm:distribution",
                "value": distribution
            })

        url = package_data.get("url")
        if url and url != "(none)":
            component["externalReferences"] = component.get("externalReferences", [])
            component["externalReferences"].append({
                "type": "website",
                "url": url
            })

        summary = package_data.get("summary")
        if summary and summary != "(none)":
            component["description"] = summary

        # Add GPG signature information if available
        signature = self.get_rpm_signature(rpm_path)
        if signature:
            # Parse signature info
            sig_props = self._parse_signature_to_properties(signature)
            properties.extend(sig_props)

        # Note: Source/patch file relationships are represented in component properties
        # (mock:source:files, mock:source:refs, mock:patch:files, mock:patch:refs)
        # but are removed from individual package components to reduce noise.
        # Source code relationships are still available in the components array.

        if properties:
            component["properties"] = properties

        # Add external reference for source RPM if available
        sourcerpm = package_data.get("sourcerpm")
        if sourcerpm and sourcerpm != "(none)":
            component["externalReferences"] = component.get("externalReferences", [])
            component["externalReferences"].append({
                "type": "distribution",
                "url": sourcerpm
            })

        return component

    def _create_toolchain_component(self, toolchain_pkg, distro_obj):
        """Creates a CycloneDX component for a build toolchain package."""
        package_name = toolchain_pkg.get("name")
        version = toolchain_pkg.get("version")

        if not package_name or not version:
            return None

        # Generate PURL and bom-ref
        purl = self._generate_purl(package_name, version, distro_obj)
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

    def _create_source_file_component(self, source_file):
        """Creates a CycloneDX component for a source file."""
        filename = source_file.get("filename")
        if not filename:
            return None

        # Generate bom-ref from filename and hash
        sha256 = source_file.get("sha256")
        if sha256:
            bom_ref = f"file:{filename}#{sha256[:16]}"
        else:
            bom_ref = f"file:{filename}"

        component = {
            "type": "file",
            "bom-ref": bom_ref,
            "name": filename
        }

        # Add hash
        sha256 = source_file.get("sha256")
        if sha256:
            component["hashes"] = [
                {
                    "alg": "SHA-256",
                    "content": sha256
                }
            ]

        # Add properties
        properties = []

        source_type = source_file.get("source_type")
        if not source_type:
            source_type = "patch" if self._is_patch_file(filename) else "source"

        properties.append({
            "name": "mock:source:type",
            "value": source_type
        })

        # Add signature information if available
        signature = source_file.get("digital_signature")
        if signature:
            if source_type == "source_rpm" and not signature.startswith("GPG signature file exists") and not signature.startswith("File is a signature file"):
                sig_props = self._parse_signature_to_properties(signature)
                properties.extend(sig_props)
            else:
                properties.append({
                    "name": "mock:signature:info",
                    "value": signature
                })

        if properties:
            component["properties"] = properties

        return component

    def _is_patch_file(self, filename):
        """Returns True if the filename looks like a patch file."""
        if not filename:
            return False
        lower_name = filename.lower()
        return (
            lower_name.startswith("patch") or
            lower_name.endswith(".patch") or
            lower_name.endswith(".diff")
        )

    def _format_epoch_timestamp(self, epoch_value):
        """Convert epoch timestamp string to ISO8601 if possible."""
        if not epoch_value or epoch_value in ("(none)", "None"):
            return None
        try:
            epoch_int = int(epoch_value)
            if epoch_int <= 0:
                return None
            return datetime.fromtimestamp(epoch_int, tz=timezone.utc).isoformat()
        except (ValueError, TypeError, OSError, OverflowError):
            return epoch_value

    def _append_source_properties(self, properties, source_entries):
        """Append source and patch references to component properties."""
        if not source_entries:
            return
        source_names = set()
        patch_names = set()
        source_refs = set()
        patch_refs = set()
        for entry in source_entries:
            filename = entry.get("filename")
            bom_ref = entry.get("bom_ref")
            entry_type = entry.get("type", "source")
            if entry_type == "patch":
                if filename:
                    patch_names.add(filename)
                if bom_ref:
                    patch_refs.add(bom_ref)
            else:
                if filename:
                    source_names.add(filename)
                if bom_ref:
                    source_refs.add(bom_ref)
        if source_names:
            properties.append({
                "name": "mock:source:files",
                "value": ",".join(sorted(source_names))
            })
        if source_refs:
            properties.append({
                "name": "mock:source:refs",
                "value": ",".join(sorted(source_refs))
            })
        if patch_names:
            properties.append({
                "name": "mock:patch:files",
                "value": ",".join(sorted(patch_names))
            })
        if patch_refs:
            properties.append({
                "name": "mock:patch:refs",
                "value": ",".join(sorted(patch_refs))
            })

    def _generate_file_bom_ref(self, package_name, package_version, file_path):
        """Generates a bom-ref for a file component within a package.

        Format: file:package-name@version:/absolute/path/to/file
        """
        # Normalize file path (ensure it starts with /)
        if not file_path.startswith('/'):
            file_path = '/' + file_path

        return f"file:{package_name}@{package_version}:{file_path}"

    def _should_include_file_dependency(self, file_path):
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

    def _create_file_components(self, rpm_path, package_name, package_version, 
                               rpm_cpe=None, rpm_gpg=None):
        """Creates file components for all files in an RPM package."""
        if not self.include_file_components:
            return []

        file_list = self.get_rpm_file_list(rpm_path)
        file_info = self.get_rpm_file_info(rpm_path)

        file_components = []
        for file_path in file_list:
            if not file_path or not file_path.strip():
                continue

            # Filter files based on configuration
            if not self.include_debug_files:
                if '/usr/lib/debug/' in file_path or file_path.endswith('.debug'):
                    continue

            file_data = file_info.get(file_path, {})
            file_hash = file_data.get("hash")
            algo_id = file_data.get("algo")

            bom_ref = self._generate_file_bom_ref(package_name, package_version, file_path)
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

    def _get_source_file_bom_refs(self, _package_name, source_files):
        """Gets bom-refs for source files that were used to build a package.

        Returns list of bom-refs for source tar.gz and patch files.
        """
        source_bom_refs = []

        for source_file in source_files:
            filename = source_file.get("filename", "")
            if not filename:
                continue

            # Include source tar.gz files
            if (
                filename.endswith('.tar.gz') or
                filename.endswith('.tar.bz2') or
                filename.endswith('.tar.xz')
            ):
                sha256 = source_file.get("sha256")
                if sha256:
                    bom_ref = f"file:{filename}#{sha256[:16]}"
                else:
                    bom_ref = f"file:{filename}"
                source_bom_refs.append(bom_ref)

            # Include patch files (matching pattern like 00xx*.patch)
            elif filename.endswith('.patch') or '.patch' in filename.lower():
                sha256 = source_file.get("sha256")
                if sha256:
                    bom_ref = f"file:{filename}#{sha256[:16]}"
                else:
                    bom_ref = f"file:{filename}"
                source_bom_refs.append(bom_ref)

        return source_bom_refs

    def _create_dependency(self, bom_ref, dependencies, component_map, distro_obj):
        """Creates a CycloneDX dependency entry."""
        if not bom_ref:
            return None

        # Convert dependency strings to bom-refs
        depends_on = []
        for dep in dependencies:
            # Parse RPM dependency format (e.g., "libc.so.6()(64bit)", "package >= 1.0")
            dep_bom_ref = self._dependency_to_bom_ref(dep, component_map, distro_obj)
            if dep_bom_ref:
                depends_on.append(dep_bom_ref)

        # Deduplicate dependsOn array
        depends_on = list(set(depends_on))

        if not depends_on:
            return None

        return {
            "ref": bom_ref,
            "dependsOn": depends_on
        }

    def _dependency_to_bom_ref(self, dependency_string, component_map, _distro):
        """Converts an RPM dependency string to a bom-ref (PURL)."""
        if not dependency_string:
            return None

        # RPM dependencies can be complex: "package >= version", "libc.so.6()(64bit)", etc.
        # Try to extract package name
        dep = dependency_string.split()[0] if dependency_string else ""

        # Remove version constraints (>=, <=, =, etc.)
        dep = re.sub(r'\s*[><=!]+\s*.*$', '', dep)

        # Remove parentheses content (e.g., "libc.so.6()(64bit)" -> "libc.so.6")
        dep = re.sub(r'\(.*?\)', '', dep)
        dep = dep.strip()

        if not dep or dep.startswith('/'):
            return None

        # Try to match against known components (case-insensitive)
        dep_lower = dep.lower()
        if dep_lower in component_map:
            return component_map[dep_lower]

        # If no match found, try to find by package name pattern
        # Some dependencies are library names, try to find matching package
        for pkg_name, bom_ref in component_map.items():
            # Check if dependency might match this package
            # (e.g., "libc.so.6" might come from "glibc" package)
            if dep_lower in pkg_name or pkg_name in dep_lower:
                return bom_ref

        # If still no match, return None (don't create invalid references)
        return None

    def _parse_signature_to_properties(self, signature_string):
        """Parses RPM signature string into CycloneDX properties."""
        properties = []
        if not signature_string or signature_string == "(none)":
            return properties

        # Parse signature like:
        # "RSA/SHA256, Fri 08 Nov 2024 03:56:24 AM EST, Key ID c8ac4916105ef944"
        properties.append({
            "name": "mock:signature:type",
            "value": "GPG"
        })

        if "RSA/SHA256" in signature_string:
            properties.append({
                "name": "mock:signature:algorithm",
                "value": "RSA/SHA256"
            })
        elif "DSA/SHA1" in signature_string:
            properties.append({
                "name": "mock:signature:algorithm",
                "value": "DSA/SHA1"
            })
        elif "ECDSA/SHA256" in signature_string:
            properties.append({
                "name": "mock:signature:algorithm",
                "value": "ECDSA/SHA256"
            })
        elif "Ed25519/SHA256" in signature_string:
            properties.append({
                "name": "mock:signature:algorithm",
                "value": "Ed25519/SHA256"
            })

        # Extract key ID
        key_id_match = re.search(r'Key ID ([0-9a-fA-F]+)', signature_string)
        if key_id_match:
            properties.append({
                "name": "mock:signature:key",
                "value": key_id_match.group(1)
            })

        # Extract date
        # Extract date
        date_match = re.search(
            r'([A-Za-z]{3} [A-Za-z]{3}\s+\d{1,2} \d{2}:\d{2}:\d{2} \d{4})', signature_string
        )
        if date_match:
            properties.append({
                "name": "mock:signature:date",
                "value": date_match.group(1)
            })

        properties.append({
            "name": "mock:signature:raw",
            "value": signature_string
        })

        return properties

    def _signature_info_to_properties(self, signature_info):
        """Converts signature info dict to CycloneDX properties."""
        properties = []

        sig_type = signature_info.get("signature_type", "unsigned")
        properties.append({
            "name": "mock:signature:type",
            "value": sig_type
        })

        if (
            sig_type not in ('unsigned', 'unknown') and
            'missing key' not in sig_type and
            'BAD' not in sig_type
        ):
            algorithm = signature_info.get("signature_algorithm")
            if algorithm:
                properties.append({
                    "name": "mock:signature:algorithm",
                    "value": algorithm
                })

            key_id = signature_info.get("signature_key")
            if key_id:
                properties.append({
                    "name": "mock:signature:key",
                    "value": key_id
                })

            sig_date = signature_info.get("signature_date")
            if sig_date:
                properties.append({
                    "name": "mock:signature:date",
                    "value": sig_date
                })

            sig_valid = signature_info.get("signature_valid", False)
            properties.append({
                "name": "mock:signature:valid",
                "value": str(sig_valid).lower()
            })

            raw_data = signature_info.get("raw_signature_data")
            if raw_data:
                properties.append({
                    "name": "mock:signature:raw",
                    "value": raw_data
                })

        return properties

    def parse_spec_file(self, spec_path):
        """Parses a spec file to extract metadata and source/patch files using the specfile library."""
        self.buildroot.root_log.debug("Parsing spec file using specfile library")
        if not os.path.isfile(spec_path):
            self.buildroot.root_log.debug(f"Spec file not found: {spec_path}")
            return {}, []

        from specfile import Specfile

        sources = []
        metadata = {}
        try:
            chroot_spec_path = self.buildroot.from_chroot_path(spec_path)
            # Use rpmspec --parse inside the build chroot to ensure macro expansion
            # matches the build environment exactly.
            cmd = ["rpmspec", "--parse", chroot_spec_path]
            result, _ = self.buildroot.doChroot(
                cmd, shell=False, returnOutput=True, printOutput=False
            )

            if not result:
                return {}, []

            # Use specfile to parse the expanded content
            spec = Specfile(content=result, sourcedir=os.path.dirname(spec_path))

            import rpm
            # Extract canonical metadata
            metadata = {
                "name": spec.expanded_name,
                "version": spec.expanded_version,
                "release": spec.expanded_release,
                "license": spec.expanded_license,
            }
            
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
                # Extract hash if present in Source (format: filename#hash)
                filename, _, hash_value = loc.partition('#')

                # Extract actual filename from URL or path
                actual_filename = os.path.basename(filename)

                # Locate the file in the SOURCES directory
                build_dir = os.path.dirname(spec_path)
                sources_dir = os.path.join(os.path.dirname(build_dir), "SOURCES")
                file_path = os.path.join(sources_dir, actual_filename)

                actual_hash = None
                if os.path.isfile(file_path):
                    actual_hash = self.hash_file(file_path)
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
        except Exception as e:
            self.buildroot.root_log.debug(f"Failed to parse spec file {spec_path}: {e}")
            self.buildroot.root_log.debug(traceback.format_exc())

        return metadata, sources

    def get_file_signature(self, file_path):
        """Attempts to detect if a file has a digital signature."""
        try:
            # Check for .asc signature file
            asc_file = file_path + ".asc"
            if os.path.isfile(asc_file):
                return "GPG signature file exists: " + os.path.basename(asc_file)

            # Check for .sig signature file
            sig_file = file_path + ".sig"
            if os.path.isfile(sig_file):
                return "GPG signature file exists: " + os.path.basename(sig_file)

            # Check if the file itself is a signature
            if file_path.endswith('.asc') or file_path.endswith('.sig'):
                return "File is a signature file"

            return None
        except OSError as e:
            self.buildroot.root_log.debug(f"Failed to check signature for {file_path}: {e}")
            return None

    def get_iso_timestamp(self):
        """Returns the current time in ISO 8601 format."""
        return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

    def get_distribution(self):
        """Returns the distribution name and version from /etc/os-release."""
        try:
            distro_name = None
            version = None
            if os.path.exists("/etc/os-release"):
                with open("/etc/os-release", encoding="utf-8") as f:
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


    def generate_cpe(self, package_name, package_version, vendor=None):
        """Generates a CPE identifier for a package."""
        # CPE format: cpe:2.3:a:{vendor}:{product}:{version}:*:*:*:*:*:*:*:*

        # Default vendor if not provided
        if not vendor or vendor == "(none)":
            vendor = "fedora"

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

    def detect_chroot_distribution(self):
        """Detects the distribution name inside the chroot using python-distro."""
        try:
            # Query the chroot filesystem directly. Attempting root_dir first.
            try:
                # pylint: disable=unexpected-keyword-arg
                distro_id = distro.id(root_dir=self.buildroot.rootdir)
            except TypeError:
                # Fallback for older python-distro versions (<1.6.0)
                # We could use os-release file directly
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
        # pylint: disable=broad-exception-caught
        except Exception as e:
            self.buildroot.root_log.debug(f"Failed to detect chroot distribution: {e}")
            return "unknown"

    def get_build_toolchain_packages(self):
        """Returns the list of packages installed in the build toolchain
        with detailed signature information collected in a single batch query."""
        try:
            # Get detailed package info including signature data in one batch query
            # Tags: Name, EVR, License, BuildTime, Signature data (RSA, DSA, GPG, PGP)
            fields = [
                "%{NAME}",
                "%{VERSION}-%{RELEASE}.%{ARCH}",
                "%{LICENSE}",
                "%{BUILDTIME}",
                "%{RSAHEADER:pgpsig}",
                "%{DSAHEADER:pgpsig}",
                "%{SIGGPG:pgpsig}",
                "%{SIGPGP:pgpsig}",
                "%{SHA256HEADER}",
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
                if len(parts) < 5:
                    continue
                
                package_name = parts[0].strip()
                package_version = parts[1].strip()
                package_license = parts[2].strip()
                build_time = parts[3].strip()
                
                # Signature data is in the middle parts
                raw_sig = None
                for sig_candidate in parts[4:8]:
                    sig_candidate = sig_candidate.strip()
                    if sig_candidate and sig_candidate != "(none)":
                        raw_sig = sig_candidate
                        break

                # Checksum is part 8, SOURCERPM is part 9
                package_checksum = parts[8].strip() if len(parts) > 8 else None
                if package_checksum == "(none)":
                    package_checksum = None
                
                source_rpm = parts[9].strip() if len(parts) > 9 else None
                if source_rpm == "(none)":
                    source_rpm = None

                # Skip GPG keys and other non-package entries
                if (
                    package_name.startswith('gpg-pubkey') or
                    package_name == '(none)' or
                    not package_name
                ):
                    continue

                # Prepare signature info structure
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

                # Build date from metadata
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
                    "licenseDeclared": package_license,
                    "digital_signature": digital_signature,
                    "sourcerpm": source_rpm,
                    "cpe": cpe,
                    "checksum": package_checksum
                })
            
            self.buildroot.root_log.debug(f"Found {len(packages)} build toolchain packages with integrated signature metadata")
            return packages
        # pylint: disable=broad-exception-caught
        except Exception as e:
            self.buildroot.root_log.debug(f"Failed to get build environment packages: {e}")
            return []

    def get_package_checksum_from_chroot(self, package_name):
        """Gets the SHA-256 checksum of an installed package from inside the chroot."""
        try:
            # Try different RPM header tags to get a checksum
            # SHA256HEADER is the SHA256 checksum of the RPM header
            cmd = ["rpm", "-q", package_name, "--qf", "%{SHA256HEADER}"]
            output, _ = self.buildroot.doChroot(
                cmd, shell=False, returnOutput=True, printOutput=False
            )

            if (
                output and output.strip() and
                output.strip() != "(none)" and
                not output.strip().startswith("error")
            ):
                return output.strip().lower()

            # Try SHA1HEADER as fallback (older RPMs)
            cmd = ["rpm", "-q", package_name, "--qf", "%{SHA1HEADER}"]
            output, _ = self.buildroot.doChroot(
                cmd, shell=False, returnOutput=True, printOutput=False
            )

            if (
                output and output.strip() and
                output.strip() != "(none)" and
                not output.strip().startswith("error")
            ):
                # It's SHA-1, but it's better than nothing
                self.buildroot.root_log.debug(
                    f"Warning: Using SHA-1 for {package_name}, SHA-256 not available"
                )
                return output.strip().lower()

            # No header checksum available
            self.buildroot.root_log.debug(f"Warning: No checksum available for {package_name}")
            return None

        # pylint: disable=broad-exception-caught
        except Exception as e:
            self.buildroot.root_log.debug(f"Failed to get checksum for package {package_name}: {e}")
            return None

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
        """Extracts metadata from an RPM file using python-rpm bindings."""
        if not os.path.isfile(rpm_path):
            self.buildroot.root_log.debug(f"RPM file not found: {rpm_path}")
            return {}

        try:
            import rpm
            ts = rpm.TransactionSet()
            with open(rpm_path, "rb") as f:
                hdr = ts.hdrFromFdno(f.fileno())

            # Map of internal names to RPM tags
            tag_map = {
                "name": rpm.RPMTAG_NAME,
                "version": rpm.RPMTAG_VERSION,
                "release": rpm.RPMTAG_RELEASE,
                "arch": rpm.RPMTAG_ARCH,
                "epoch": rpm.RPMTAG_EPOCH,
                "summary": rpm.RPMTAG_SUMMARY,
                "license": rpm.RPMTAG_LICENSE,
                "vendor": rpm.RPMTAG_VENDOR,
                "url": rpm.RPMTAG_URL,
                "packager": rpm.RPMTAG_PACKAGER,
                "buildtime": rpm.RPMTAG_BUILDTIME,
                "buildhost": rpm.RPMTAG_BUILDHOST,
                "sourcerpm": rpm.RPMTAG_SOURCERPM,
                "group": rpm.RPMTAG_GROUP,
                "distribution": rpm.RPMTAG_DISTRIBUTION,
                "sha256": rpm.RPMTAG_SHA256HEADER
            }

            metadata = {}
            for field_name, tag in tag_map.items():
                value = hdr[tag]
                
                # Special handling for certain types
                if field_name == "epoch" and value is None:
                    value = "(none)"
                elif value is None:
                    value = ""
                elif isinstance(value, bytes):
                    value = value.decode('utf-8', errors='replace')
                
                metadata[field_name] = str(value)

            self.buildroot.root_log.debug(f"RPM metadata extracted natively: {metadata['name']}-{metadata['version']}")
            return metadata

        except Exception as e:
            self.buildroot.root_log.debug(f"Failed to extract RPM metadata from {rpm_path} natively: {e}")
            # Fallback to subprocess if native method fails (should be rare)
            return self._get_rpm_metadata_subprocess(rpm_path)

    def _get_rpm_metadata_subprocess(self, rpm_path):
        """Fallback method to extract metadata using rpm command-line."""
        metadata = {}
        fields = {
            "name": "%{NAME}", "version": "%{VERSION}", "release": "%{RELEASE}",
            "arch": "%{ARCH}", "epoch": "%{EPOCH}", "summary": "%{SUMMARY}",
            "license": "%{LICENSE}", "vendor": "%{VENDOR}", "url": "%{URL}",
            "packager": "%{PACKAGER}", "buildtime": "%{BUILDTIME}",
            "buildhost": "%{BUILDHOST}", "sourcerpm": "%{SOURCERPM}",
            "group": "%{GROUP}", "distribution": "%{DISTRIBUTION}"
        }
        try:
            for field_name, field_format in fields.items():
                cmd = ["rpm", "-qp", rpm_path, "--queryformat", field_format]
                result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True)
                value = result.stdout.strip()
                if field_name == "epoch" and not value:
                    value = "(none)"
                metadata[field_name] = value
            return metadata
        # pylint: disable=broad-exception-caught
        except Exception as e:
            self.buildroot.root_log.debug(f"Failed to extract RPM metadata via subprocess for {rpm_path}: {e}")
            return {}

    def get_rpm_file_list(self, rpm_path):
        """Extracts the list of files from an RPM file."""
        cmd = ["rpm", "-qpl", rpm_path]
        try:
            result = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True
            )
            files = result.stdout.splitlines()
            self.buildroot.root_log.debug(f"Files in RPM {rpm_path}: {files}")
            return files
        except subprocess.CalledProcessError as e:
            self.buildroot.root_log.debug(f"Failed to get file list for {rpm_path}: {e.stderr}")
            return []

    def get_rpm_file_info(self, rpm_path):
        """Extracts file hashes, ownership, and permissions from an RPM file using rpm-python."""
        # pylint: disable=no-member
        file_info = {}
        try:
            ts = rpm.TransactionSet()
            # pylint: disable=protected-access
            ts.setVSFlags(rpm._RPMVSF_NOSIGNATURES | rpm._RPMVSF_NODIGESTS)
            # pylint: enable=protected-access
            with open(rpm_path, "rb") as f:
                hdr = ts.hdrFromFdno(f.fileno())

            # Use dirnames/basenames/dirindexes to construct paths reliably
            dirnames = hdr[rpm.RPMTAG_DIRNAMES]
            basenames = hdr[rpm.RPMTAG_BASENAMES]
            dirindexes = hdr[rpm.RPMTAG_DIRINDEXES]

            filedigests = hdr[rpm.RPMTAG_FILEDIGESTS]
            filemodes = hdr[rpm.RPMTAG_FILEMODES]
            fileusernames = hdr[rpm.RPMTAG_FILEUSERNAME]
            filegroupnames = hdr[rpm.RPMTAG_FILEGROUPNAME]
            
            # Detect digest algorithm
            try:
                algo = hdr[rpm.RPMTAG_FILEDIGESTALGO]
            except (KeyError, IndexError):
                algo = 8  # Default to SHA256

            for i, basename in enumerate(basenames):
                dirname = dirnames[dirindexes[i]]

                # Decode bytes to strings if needed
                if isinstance(dirname, bytes):
                    dirname = dirname.decode('utf-8', 'replace')
                if isinstance(basename, bytes):
                    basename = basename.decode('utf-8', 'replace')

                filename = os.path.join(dirname, basename)

                digest = filedigests[i]
                if isinstance(digest, bytes):
                    digest = digest.decode('utf-8')

                # Empty digest usually means empty string or all zeros
                if not digest:
                    digest = None

                mode = filemodes[i]
                # Format permissions as octal string
                permissions = f"0{mode:o}"

                owner = fileusernames[i]
                if isinstance(owner, bytes):
                    owner = owner.decode('utf-8', 'replace')

                group = filegroupnames[i]
                if isinstance(group, bytes):
                    group = group.decode('utf-8', 'replace')

                file_info[filename] = {
                    "hash": digest,
                    "algo": algo,
                    "permissions": permissions,
                    "owner": owner,
                    "group": group
                }

            self.buildroot.root_log.debug(
                f"File info for RPM {rpm_path}: {len(file_info)} files processed (Algo: {algo})"
            )
            return file_info

        # pylint: disable=broad-exception-caught
        except Exception as e:
            self.buildroot.root_log.debug(f"Failed to get file info for {rpm_path}: {e}")
            self.buildroot.root_log.debug(traceback.format_exc())
            return {}

    def get_rpm_dependencies(self, rpm_path):
        """Extracts the list of dependencies from an RPM file natively."""
        try:
            import rpm
            ts = rpm.TransactionSet()
            with open(rpm_path, "rb") as f:
                hdr = ts.hdrFromFdno(f.fileno())
            
            # Use rpm.labelCompare etc to format if needed, but for now 
            # we just extract the requirement names.
            requirements = hdr[rpm.RPMTAG_REQUIRENAME]
            if not requirements:
                return []
            
            # Convert bytes to strings
            return [r.decode('utf-8', 'replace') if isinstance(r, bytes) else str(r) for r in requirements]
        except Exception as e:
            self.buildroot.root_log.debug(f"Failed to extract dependencies natively for {rpm_path}: {e}")
            try:
                cmd = ["rpm", "-qpR", rpm_path]
                result = subprocess.run(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True
                )
                return result.stdout.splitlines()
            except Exception:
                return []

    def get_rpm_signature(self, rpm_path):
        """Extracts the GPG signature of an RPM file."""
        # Try subprocess first as it's more reliable for getting the formatted string
        try:
            # Try to get it via queryformat first (most machine-readable if successful)
            cmd = ["rpm", "-qp", "--queryformat", "%{SIGPGP:pgpsig} %{SIGGPG:pgpsig}", rpm_path]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True)
            sig = result.stdout.strip()
            if sig and sig != "(none) (none)" and sig != "(none)":
                return sig.replace("(none)", "").strip()

            # Fallback to parsing rpm -qip output (always works for human-readable)
            cmd = ["rpm", "-qip", rpm_path]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True)
            for line in result.stdout.splitlines():
                if "Signature" in line and ":" in line:
                    sig_val = line.split(":", 1)[1].strip()
                    if sig_val and sig_val != "(none)":
                        return sig_val

            return None
        except Exception as e:
            self.buildroot.root_log.debug(f"Failed to extract signature for {rpm_path}: {e}")
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
        self.buildroot.root_log.debug(f"Extracting source metadata from source RPM: {src_rpm_path}")
        source_files = []
        if not os.path.isfile(src_rpm_path):
            return source_files
        try:
            import rpm
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


    def _generate_spdx_document(self, name, version, release, build_dir, rpm_files,
                                source_files, toolchain_components, distro_id, spec_metadata=None):
        """Generates the full SPDX document."""
        doc_spdx_id = "SPDXRef-DOCUMENT"
        creation_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Basic Document Structure
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

        # Add Toolchain Packages
        for tc in toolchain_components:
            spdx_pkg = self._create_spdx_package_from_dict(tc)
            if spdx_pkg:
                document["packages"].append(spdx_pkg)
                # Relationship: Document DESCRIBES toolchain (conceptually part of build environment)
                # But strictly, Document DESCRIBES the output artifacts.
                # We'll just list them.

        # Add Source Files
        for src_file in source_files:
            spdx_file = self._create_spdx_file(src_file)
            if spdx_file:
                document["files"].append(spdx_file)
                # Relationship: Document CONTAINS file
                document["relationships"].append({
                    "spdxElementId": doc_spdx_id,
                    "relatedSpdxElement": spdx_file["SPDXID"],
                    "relationshipType": "CONTAINS"
                })

        # Prepare toolchain name to SPDXID map for relationships
        tc_name_to_id = {}
        if spec_metadata and toolchain_components:
            for tc in toolchain_components:
                pkg_name = tc.get("name")
                pkg_version = tc.get("version")
                if pkg_name and pkg_version:
                    safe_name = re.sub(r'[^a-zA-Z0-9.-]', '-', pkg_name)
                    safe_ver = re.sub(r'[^a-zA-Z0-9.-]', '-', pkg_version)
                    tc_name_to_id[pkg_name.lower()] = f"SPDXRef-Package-{safe_name}-{safe_ver}"

        # Add Build Artifacts (RPMs)
        for rpm_file in rpm_files:
            rpm_path = os.path.join(build_dir, rpm_file)
            spdx_pkg = self._create_spdx_package_from_rpm(rpm_path, distro_id)
            if spdx_pkg:
                document["packages"].append(spdx_pkg)
                # Relationship: Document DESCRIBES Package
                document["relationships"].append({
                    "spdxElementId": doc_spdx_id,
                    "relatedSpdxElement": spdx_pkg["SPDXID"],
                    "relationshipType": "DESCRIBES"
                })

                # Add BUILD_DEPENDENCY_OF relationships
                if spec_metadata:
                    build_reqs = spec_metadata.get("build_requires", [])
                    for req in build_reqs:
                        req_name = req.split()[0].lower()
                        if req_name in tc_name_to_id:
                            document["relationships"].append({
                                "spdxElementId": tc_name_to_id[req_name],
                                "relatedSpdxElement": spdx_pkg["SPDXID"],
                                "relationshipType": "BUILD_DEPENDENCY_OF"
                            })

        return document

    def _create_spdx_package_from_rpm(self, rpm_path, distro_obj):
        """Creates an SPDX Package from an RPM file."""
        pkg_data = self.get_rpm_metadata(rpm_path)
        if not pkg_data:
            return None

        name = pkg_data.get("name")
        version = pkg_data.get("version")
        release = pkg_data.get("release")
        arch = pkg_data.get("arch")
        full_version = f"{version}-{release}" if release else version

        safe_name = re.sub(r'[^a-zA-Z0-9.-]', '-', name)
        safe_ver = re.sub(r'[^a-zA-Z0-9.-]', '-', full_version)
        spdx_id = f"SPDXRef-Package-{safe_name}-{safe_ver}"

        package = {
            "name": name,
            "SPDXID": spdx_id,
            "versionInfo": full_version,
            "downloadLocation": "NOASSERTION",
            "filesAnalyzed": False,
            "supplier": "NOASSERTION"
        }

        # License
        lic = pkg_data.get("license")
        if lic and lic != "(none)":
            package["licenseDeclared"] = lic
        else:
            package["licenseDeclared"] = "NOASSERTION"
        package["licenseConcluded"] = "NOASSERTION"

        # Supplier
        packager = pkg_data.get("packager")
        if packager and packager != "(none)":
            package["supplier"] = f"Person: {packager}"

        # Checksums
        rpm_hash = pkg_data.get("sha256")
        if not rpm_hash or rpm_hash == "(none)":
            rpm_hash = self.hash_file(rpm_path)
            
        if rpm_hash:
            package["checksums"] = [{
                "algorithm": "SHA256",
                "checksumValue": rpm_hash
            }]

        # External Refs
        external_refs = []
        purl = self._generate_purl(name, full_version, distro_obj, arch)
        if purl:
            external_refs.append({
                "referenceCategory": "PACKAGE-MANAGER",
                "referenceType": "purl",
                "referenceLocator": purl
            })

        vendor = pkg_data.get("vendor")
        cpe = self.generate_cpe(name, version, vendor=vendor)
        if cpe:
            external_refs.append({
                "referenceCategory": "SECURITY",
                "referenceType": "cpe23Type",
                "referenceLocator": cpe
            })

        if external_refs:
            package["externalRefs"] = external_refs

        return package

    def _create_spdx_package_from_dict(self, pkg_data):
        """Creates an SPDX Package from a dictionary (e.g. toolchain)."""
        name = pkg_data.get("name")
        version = pkg_data.get("version")
        if not name or not version:
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

        checksum = pkg_data.get("checksum")
        if checksum and not checksum.startswith("error"):
            # Assume SHA256 if len 64 else SHA1
            alg = "SHA256" if len(checksum) == 64 else "SHA1"
            package["checksums"] = [{
                "algorithm": alg,
                "checksumValue": checksum
            }]

        return package

    def _create_spdx_file(self, file_data):
        """Creates an SPDX File from file metadata."""
        filename = file_data.get("filename")
        if not filename:
            return None

        safe_name = re.sub(r'[^a-zA-Z0-9.-]', '-', filename)
        spdx_id = f"SPDXRef-File-{safe_name}"

        file_obj = {
            "fileName": f"./{filename}",
            "SPDXID": spdx_id,
            "licenseConcluded": "NOASSERTION",
            "copyrightText": "NOASSERTION"
        }

        sha256 = file_data.get("sha256")
        if sha256:
            file_obj["checksums"] = [{
                "algorithm": "SHA256",
                "checksumValue": sha256
            }]

        return file_obj
