# Copyright (C) 2025, Atomicorp, Inc.
# SPDX-License-Identifier: GPL-2.0-only

import os
import json
import subprocess
from mockbuild.trace_decorator import traceLog
import hashlib
import re
import socket
import uuid
import tempfile
import shutil
import shlex

requires_api_version = "1.1"  # Ensure compatibility with mock API

# Plugin entry point
@traceLog()
def init(plugins, conf, buildroot):
    # Ensure configuration exists for the plugin
    if "sbom_generator_opts" not in conf:
        conf["sbom_generator_opts"] = {}
    SBOMGenerator(plugins, conf["sbom_generator_opts"], buildroot)

class SBOMGenerator(object):
    """Generates SBOM for the built packages."""
    # pylint: disable=too-few-public-methods
    @traceLog()
    def __init__(self, plugins, conf, buildroot):

        self.buildroot = buildroot
        self.state = buildroot.state
        self.rootdir = buildroot.rootdir
        self.builddir = buildroot.builddir
        self.conf = conf
        self.sbom_enabled = self.conf.get('generate_sbom', True)
        self.sbom_done = False
        
        # Configuration options for file-level dependencies and filtering
        self.include_file_dependencies = self.conf.get('include_file_dependencies', False)
        self.include_file_components = self.conf.get('include_file_components', True)
        self.include_debug_files = self.conf.get('include_debug_files', False)
        self.include_man_pages = self.conf.get('include_man_pages', True)
        self.include_source_dependencies = self.conf.get('include_source_dependencies', True)
        self.include_toolchain_dependencies = self.conf.get('include_toolchain_dependencies', False)
        
        plugins.add_hook("prebuild", self._listSPECSDirectory)
        plugins.add_hook("postbuild", self._generateSBOMPostBuildHook)

    @traceLog()
    def _listSPECSDirectory(self):
        """Lists the contents of the SPECS directory before building."""

        print("DEBUG: Listing contents of SPECS directory before building:")
        print(f"DEBUG: builddir is {self.buildroot.builddir}")
        print(f"DEBUG: rootdir is {self.rootdir}")
        print(f"DEBUG: resultsdir is {self.buildroot.resultdir}")

        # Look for spec file in the build directory
        build_dir = self.buildroot.builddir
        specs_dir = os.path.join(build_dir, "SPECS")
        print(f"DEBUG: spec dir is {specs_dir}")

        try:
            if os.path.exists(specs_dir):
                specs_files = os.listdir(specs_dir)
                print(f"Contents of SPECS directory: {specs_files}")
            else:
                print("SPECS directory does not exist.")
        except Exception as e:
            print(f"Failed to list contents of SPECS directory: {e}")

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
        from datetime import datetime
        
        metadata = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "tools": [
                {
                    "vendor": "Mock",
                    "name": "mock-sbom-generator",
                            "version": "1.2.5"
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
        
        distro = self.get_distribution()
        if distro:
            properties.append({
                "name": "mock:build:distribution",
                "value": distro
            })
        
        # Add chroot information if available
        if hasattr(self.buildroot, 'rootdir') and self.buildroot.rootdir:
            properties.append({
                "name": "mock:build:chroot",
                "value": self.buildroot.rootdir
            })
        
        # Add Mock config if available
        if hasattr(self.buildroot, 'config') and self.buildroot.config:
            config_name = self.buildroot.config.get('config_path', 'unknown')
            properties.append({
                "name": "mock:build:config",
                "value": config_name
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
                print(f"Warning: failed to eval macro {macro} in chroot: {exc}")
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
            print(f"Warning: failed to eval macro {macro}: {exc}")
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
                token in flag_union for token in ["-fpie", "-fpie", "-pie"]
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

    def _generate_purl(self, package_name, version, distro=None, arch=None):
        """Generate Package URL (PURL) for RPM package."""
        if not distro:
            distro = self.detect_chroot_distribution() or "fedora"
        
        # Clean package name for PURL (lowercase, no special chars)
        clean_name = re.sub(r'[^a-zA-Z0-9._-]', '-', package_name.lower())
        
        purl = f"pkg:rpm/{distro}/{clean_name}@{version}"
        if arch:
            purl += f"?arch={arch}"
        return purl

    def _generate_bom_ref(self, package_name, version, component_type="package"):
        """Generate a unique bom-ref identifier for a component."""
        # Use PURL as bom-ref for consistency
        distro = self.detect_chroot_distribution() or "fedora"
        return self._generate_purl(package_name, version, distro)

    @traceLog()
    def _generateSBOMPostBuildHook(self):
        if self.sbom_done or not self.sbom_enabled:
            return

        state_text = "Generating CycloneDX SBOM for built packages v1.0"
        self.state.start(state_text)

        try:
            build_dir = self.buildroot.resultdir
            # Filter out source RPMs from binary RPM processing
            rpm_files = [f for f in os.listdir(build_dir) if f.endswith('.rpm') and not f.endswith('.src.rpm')]
            src_rpm_files = [f for f in os.listdir(build_dir) if f.endswith('.src.rpm')]
            
            # Look for spec file in the build directory (during build process)
            build_build_dir = os.path.join(self.buildroot.rootdir, "builddir/build")
            spec_file = None
            if os.path.exists(build_build_dir):
                # Look for spec file in the build directory
                for root, dirs, files in os.walk(build_build_dir):
                    for file in files:
                        if file.endswith('.spec'):
                            spec_file = os.path.join(root, file)
                            break
                    if spec_file:
                        break

            if not rpm_files and not src_rpm_files and not spec_file:
                print("No RPM, source RPM, or spec file found for SBOM generation.")
                return

            # Create CycloneDX document
            bom = self._create_cyclonedx_document()
            
            # Get build toolchain packages
            build_toolchain_packages = self.get_build_toolchain_packages()
            
            # Process source files from spec file
            source_files = []
            source_component_entries = []
            build_subject_name = None
            build_subject_version = None
            build_subject_release = None

            if spec_file:
                build_subject_name = os.path.splitext(os.path.basename(spec_file))[0]
                parsed_sources = self.parse_spec_file(spec_file)
                if parsed_sources:
                    source_files = parsed_sources

            srpm_metadata = None
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
            
            # Construct output filename using package name-version-release format
            # These should always be available in a proper mock build
            if not build_subject_name or not build_subject_version or not build_subject_release:
                print(f"WARNING: Missing package metadata - name: {build_subject_name}, version: {build_subject_version}, release: {build_subject_release}")
                print("Cannot generate SBOM with proper filename - build metadata incomplete")
                return
            
            sbom_filename = f"{build_subject_name}-{build_subject_version}-{build_subject_release}.sbom"
            out_file = os.path.join(self.buildroot.resultdir, sbom_filename)

            if not source_files and src_rpm_files:
                # Extract from source RPM if available
                src_rpm_path = os.path.join(build_dir, src_rpm_files[0])
                source_files = self.extract_source_files_from_srpm(src_rpm_path)

            # Convert source files to CycloneDX components
            for source_file in source_files:
                component = self._create_source_file_component(source_file)
                if component:
                    bom["components"].append(component)
                    filename = source_file.get("filename")
                    source_component_entries.append({
                        "filename": filename,
                        "bom_ref": component.get("bom-ref"),
                        "type": "patch" if self._is_patch_file(filename) else "source"
                    })

            # Convert build toolchain packages to components
            distro = self.detect_chroot_distribution() or "fedora"
            toolchain_bom_refs = []
            for toolchain_pkg in build_toolchain_packages:
                component = self._create_toolchain_component(toolchain_pkg, distro)
                if component:
                    bom_ref = component.get("bom-ref")
                    if bom_ref:
                        toolchain_bom_refs.append(bom_ref)
                    bom["components"].append(component)

            # Process binary RPMs and convert to components
            built_package_bom_refs = []
            component_map = {}  # Map package names to bom-refs for dependency resolution
            primary_rpm_metadata = None  # Store metadata from primary package for metadata enhancement
            
            # Build component map from toolchain packages
            for toolchain_pkg in build_toolchain_packages:
                pkg_name = toolchain_pkg.get("name")
                pkg_version = toolchain_pkg.get("version")
                if pkg_name and pkg_version:
                    purl = self._generate_purl(pkg_name, pkg_version, distro)
                    component_map[pkg_name.lower()] = purl
            
            for rpm_file in rpm_files:
                rpm_path = os.path.join(build_dir, rpm_file)
                component = self._create_built_package_component(rpm_path, distro, source_component_entries)
                if component:
                    bom_ref = component.get("bom-ref")
                    package_name = component.get("name")
                    package_version = component.get("version")
                    if bom_ref:
                        built_package_bom_refs.append(bom_ref)
                        # Add to component map for dependency resolution
                        if package_name:
                            component_map[package_name.lower()] = bom_ref
                    bom["components"].append(component)
                    
                    # Store metadata from primary package (prefer main package matching build subject)
                    if not primary_rpm_metadata:
                        # Prefer the main package over debuginfo packages
                        if not package_name or 'debuginfo' not in package_name.lower():
                            primary_rpm_metadata = self.get_rpm_metadata(rpm_path)
                    else:
                        # If we have metadata, check if we should replace it with a better match
                        current_name = primary_rpm_metadata.get('name', '').lower()
                        is_current_debuginfo = 'debuginfo' in current_name
                        is_current_main = build_subject_name and current_name == build_subject_name.lower()
                        
                        # Replace if: current is debuginfo and new is not, OR new matches build subject name
                        should_replace = False
                        if is_current_debuginfo and package_name and 'debuginfo' not in package_name.lower():
                            should_replace = True
                        elif build_subject_name and package_name and package_name.lower() == build_subject_name.lower():
                            # New package matches build subject name - always prefer it
                            should_replace = True
                        
                        if should_replace:
                            primary_rpm_metadata = self.get_rpm_metadata(rpm_path)
                    
                    # Create file components for files within this package
                    if package_name and package_version and self.include_file_components:
                        file_components = self._create_file_components(rpm_path, package_name, package_version)
                        for file_comp in file_components:
                            bom["components"].append(file_comp)
                            # Create dependency: file depends on package (only if configured)
                            if self._should_include_file_dependency(file_comp.get("name", "")):
                                file_dep = {
                                    "ref": file_comp["bom-ref"],
                                    "dependsOn": [bom_ref]
                                }
                                bom["dependencies"].append(file_dep)
                    
                    # Create dependency entry for runtime dependencies (libraries/RPMs)
                    dependencies = self.get_rpm_dependencies(rpm_path)
                    runtime_dependency = self._create_dependency(bom_ref, dependencies, component_map, distro)
                    
                    # Build dependsOn array with runtime dependencies and optionally toolchain
                    all_depends_on = []
                    
                    # Add runtime dependencies (libraries/RPMs this package depends on)
                    if runtime_dependency and runtime_dependency.get("dependsOn"):
                        for dep_ref in runtime_dependency.get("dependsOn", []):
                            if dep_ref not in all_depends_on:
                                all_depends_on.append(dep_ref)
                    
                    # Add toolchain dependencies if configured (build-time dependencies)
                    if self.include_toolchain_dependencies and toolchain_bom_refs:
                        for toolchain_ref in toolchain_bom_refs:
                            if toolchain_ref not in all_depends_on:
                                all_depends_on.append(toolchain_ref)
                    
                    # Deduplicate final dependsOn array
                    all_depends_on = list(set(all_depends_on))
                    
                    # Create dependency entry if we have any dependencies
                    if all_depends_on:
                        combined_dep = {
                            "ref": bom_ref,
                            "dependsOn": all_depends_on
                        }
                        bom["dependencies"].append(combined_dep)
                    elif runtime_dependency:
                        # Fall back to just runtime dependencies if no other deps
                        bom["dependencies"].append(runtime_dependency)
                    
                    # Note: Source code relationships are represented in component properties
                    # (mock:source:files, mock:source:refs, mock:patch:files, mock:patch:refs)
                    # rather than in dependencies, as source code is a build input, not a runtime dependency

            # Add RPM-specific metadata to metadata.properties
            if primary_rpm_metadata:
                rpm_props = bom["metadata"]["properties"]
                
                # Add buildhost if available
                buildhost = primary_rpm_metadata.get("buildhost")
                if buildhost and buildhost != "(none)":
                    rpm_props.append({
                        "name": "mock:rpm:buildhost",
                        "value": buildhost
                    })
                
                # Add buildtime if available
                buildtime = primary_rpm_metadata.get("buildtime")
                if buildtime and buildtime != "(none)":
                    rpm_props.append({
                        "name": "mock:rpm:buildtime",
                        "value": buildtime
                    })
                
                # Add source RPM if available
                sourcerpm = primary_rpm_metadata.get("sourcerpm")
                if sourcerpm and sourcerpm != "(none)":
                    rpm_props.append({
                        "name": "mock:rpm:sourcerpm",
                        "value": sourcerpm
                    })
                
                # Add group if available
                group = primary_rpm_metadata.get("group")
                if group and group != "(none)":
                    rpm_props.append({
                        "name": "mock:rpm:group",
                        "value": group
                    })
                
                # Add epoch if available and not empty
                epoch = primary_rpm_metadata.get("epoch")
                if epoch and epoch != "(none)" and epoch.strip():
                    rpm_props.append({
                        "name": "mock:rpm:epoch",
                        "value": epoch
                    })
                
                # Add distribution if available
                distribution = primary_rpm_metadata.get("distribution")
                if distribution and distribution != "(none)":
                    rpm_props.append({
                        "name": "mock:rpm:distribution",
                        "value": distribution
                    })
                
                # Add manufacture field if vendor is available
                vendor = primary_rpm_metadata.get("vendor")
                if vendor and vendor != "(none)":
                    bom["metadata"]["manufacture"] = {
                        "name": vendor
                    }
                    # Also add as authors (sbomqs expects this)
                    bom["metadata"]["authors"] = [
                        {
                            "name": vendor
                        }
                    ]
                
                # Add supplier (from Packager field)
                packager = primary_rpm_metadata.get("packager")
                if packager and packager != "(none)":
                    bom["metadata"]["supplier"] = {
                        "name": packager
                    }
            
            # Add metadata.component representing what this SBOM is about
            # Use the primary built package(s) or create an aggregate component
            if built_package_bom_refs:
                # For single package builds, use that package
                # For multi-package builds, use the first/main package or create aggregate
                if len(built_package_bom_refs) == 1:
                    # Single package: use it as the component
                    primary_ref = built_package_bom_refs[0]
                    primary_component = next((c for c in bom["components"] if c.get("bom-ref") == primary_ref), None)
                    if primary_component:
                        component_obj = {
                            "type": primary_component.get("type", "application"),
                            "name": primary_component.get("name"),
                            "version": primary_component.get("version"),
                            "bom-ref": primary_ref,
                            "purl": primary_component.get("purl")
                        }
                        
                        # Add description if available
                        if primary_component.get("description"):
                            component_obj["description"] = primary_component.get("description")
                        elif primary_rpm_metadata:
                            summary = primary_rpm_metadata.get("summary")
                            if summary and summary != "(none)":
                                component_obj["description"] = summary
                        
                        # Add externalReferences
                        external_refs = []
                        if primary_rpm_metadata:
                            # Add source RPM reference
                            sourcerpm = primary_rpm_metadata.get("sourcerpm")
                            if sourcerpm and sourcerpm != "(none)":
                                external_refs.append({
                                    "type": "distribution",
                                    "url": sourcerpm
                                })
                            # Add project URL
                            url = primary_rpm_metadata.get("url")
                            if url and url != "(none)":
                                external_refs.append({
                                    "type": "website",
                                    "url": url
                                })
                        if external_refs:
                            component_obj["externalReferences"] = external_refs
                        
                        # Add license information
                        if primary_component.get("licenses"):
                            component_obj["licenses"] = primary_component.get("licenses")
                        elif primary_rpm_metadata:
                            license_str = primary_rpm_metadata.get("license")
                            if license_str and license_str != "(none)":
                                component_obj["licenses"] = [
                                    {
                                        "license": {
                                            "id": license_str
                                        }
                                    }
                                ]
                        
                        bom["metadata"]["component"] = component_obj
                else:
                    # Multi-package build: create aggregate component that represents the full build output
                    first_pkg = next((c for c in bom["components"] if c.get("bom-ref") == built_package_bom_refs[0]), None)
                    if first_pkg:
                        aggregate_name = build_subject_name or first_pkg.get("name", "unknown")
                        aggregate_version = None
                        if build_subject_version and build_subject_release:
                            aggregate_version = f"{build_subject_version}-{build_subject_release}"
                        elif primary_rpm_metadata:
                            meta_version = primary_rpm_metadata.get("version")
                            meta_release = primary_rpm_metadata.get("release")
                            if meta_version and meta_release:
                                aggregate_version = f"{meta_version}-{meta_release}"
                        if not aggregate_version:
                            aggregate_version = first_pkg.get("version", "unknown")

                        # Build description - prefer summary from RPM, fall back to generic description
                        description = f"Build output containing {len(built_package_bom_refs)} package(s)"
                        if primary_rpm_metadata:
                            summary = primary_rpm_metadata.get("summary")
                            if summary and summary != "(none)":
                                description = f"{summary} (build output containing {len(built_package_bom_refs)} package(s))"
                        
                        component_obj = {
                            "type": "application",
                            "name": aggregate_name,
                            "version": aggregate_version,
                            "bom-ref": f"build-output:{aggregate_name}",
                            "description": description
                        }
                        
                        if aggregate_name and aggregate_version:
                            component_obj["purl"] = self._generate_purl(aggregate_name, aggregate_version, distro)
                        elif first_pkg.get("purl"):
                            component_obj["purl"] = first_pkg.get("purl")
                        
                        # Add externalReferences
                        external_refs = []
                        if primary_rpm_metadata:
                            # Add source RPM reference
                            sourcerpm = primary_rpm_metadata.get("sourcerpm")
                            if sourcerpm and sourcerpm != "(none)":
                                external_refs.append({
                                    "type": "distribution",
                                    "url": sourcerpm
                                })
                            # Add project URL
                            url = primary_rpm_metadata.get("url")
                            if url and url != "(none)":
                                external_refs.append({
                                    "type": "website",
                                    "url": url
                                })
                        if external_refs:
                            component_obj["externalReferences"] = external_refs
                        
                        # Add license information
                        if first_pkg.get("licenses"):
                            component_obj["licenses"] = first_pkg.get("licenses")
                        elif primary_rpm_metadata:
                            license_str = primary_rpm_metadata.get("license")
                            if license_str and license_str != "(none)":
                                component_obj["licenses"] = [
                                    {
                                        "license": {
                                            "id": license_str
                                        }
                                    }
                                ]
                        
                        bom["metadata"]["component"] = component_obj

            # Add dependency entries for all components that don't have them
            # CycloneDX requires every component to have a dependency entry
            # Use dictionary to ensure uniqueness (no duplicates)
            dependencies_dict = {}
            
            # Start with existing dependencies (from built packages)
            for dep in bom["dependencies"]:
                ref = dep.get("ref")
                if ref:
                    dependencies_dict[ref] = dep
            
            # Add entries for source file components (no dependencies)
            for source_entry in source_component_entries:
                bom_ref = source_entry.get("bom_ref")
                if bom_ref and bom_ref not in dependencies_dict:
                    dependencies_dict[bom_ref] = {
                        "ref": bom_ref,
                        "dependsOn": []
                    }
            
            # Add entries for toolchain components (no dependencies tracked for now)
            for toolchain_pkg in build_toolchain_packages:
                pkg_name = toolchain_pkg.get("name")
                pkg_version = toolchain_pkg.get("version")
                if pkg_name and pkg_version:
                    purl = self._generate_purl(pkg_name, pkg_version, distro)
                    if purl and purl not in dependencies_dict:
                        dependencies_dict[purl] = {
                            "ref": purl,
                            "dependsOn": []
                        }
            
            # Add entries for any remaining components
            # (in case we have components that weren't explicitly handled)
            for component in bom["components"]:
                comp_bom_ref = component.get("bom-ref")
                if comp_bom_ref and comp_bom_ref not in dependencies_dict:
                    dependencies_dict[comp_bom_ref] = {
                        "ref": comp_bom_ref,
                        "dependsOn": []
                    }
            
            # Replace dependencies array with deduplicated list
            bom["dependencies"] = list(dependencies_dict.values())

            # Write CycloneDX BOM
            with open(out_file, "w") as f:
                json.dump(bom, f, indent=2)

            print(f"CycloneDX SBOM successfully written to: {out_file}")
        except Exception as e:
            print(f"An error occurred during SBOM generation: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.sbom_done = True
            self.state.finish(state_text)

    def _create_built_package_component(self, rpm_path, distro, source_components=None):
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
        purl = self._generate_purl(package_name, full_version, distro, arch)
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
        cpe = self.generate_cpe(package_name, version)
        if cpe:
            component["externalReferences"] = [
                {
                    "type": "other",
                    "comment": "CPE 2.3",
                    "url": cpe
                }
            ]
        
        # Add hash of RPM file
        rpm_hash = self.hash_file(rpm_path)
        if rpm_hash:
            component["hashes"] = [
                {
                    "alg": "SHA-256",
                    "content": rpm_hash
                }
            ]
        
        # Add license information
        license_str = package_data.get("license")
        if license_str and license_str != "(none)":
            component["licenses"] = [
                {
                    "license": {
                        "id": license_str
                    }
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

        sourcerpm = package_data.get("sourcerpm")
        if sourcerpm and sourcerpm != "(none)":
            properties.append({
                "name": "mock:rpm:sourcerpm",
                "value": sourcerpm
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
        if sourcerpm and sourcerpm != "(none)":
            component["externalReferences"] = component.get("externalReferences", [])
            component["externalReferences"].append({
                "type": "distribution",
                "url": sourcerpm
            })
        
        return component

    def _create_toolchain_component(self, toolchain_pkg, distro):
        """Creates a CycloneDX component for a build toolchain package."""
        package_name = toolchain_pkg.get("name")
        version = toolchain_pkg.get("version")
        
        if not package_name or not version:
            return None
        
        # Generate PURL and bom-ref
        purl = self._generate_purl(package_name, version, distro)
        bom_ref = purl
        
        component = {
            "type": "library",
            "bom-ref": bom_ref,
            "name": package_name,
            "version": version,
            "purl": purl
        }
        
        # Add checksum if available
        checksum = toolchain_pkg.get("checksum")
        if checksum and checksum != "error" and not checksum.startswith("error"):
            # Determine algorithm based on hash length
            if len(checksum) == 64:
                alg = "SHA-256"
            elif len(checksum) == 40:
                alg = "SHA-1"
            else:
                alg = "SHA-256"  # Default assumption
            
            component["hashes"] = [
                {
                    "alg": alg,
                    "content": checksum
                }
            ]
        
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
                    "license": {
                        "id": license_str
                    }
                }
            ]
        
        # Add properties
        properties = []
        
        # Mark as build toolchain
        properties.append({
            "name": "mock:role",
            "value": "build-toolchain"
        })
        
        # Add signature information
        signature_info = toolchain_pkg.get("digital_signature", {})
        if signature_info:
            sig_props = self._signature_info_to_properties(signature_info)
            properties.extend(sig_props)
        
        # Add build date if available
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
        if sha256:
            component["hashes"] = [
                {
                    "alg": "SHA-256",
                    "content": sha256
                }
            ]
        
        # Add properties
        properties = []
        
        source_type = "patch" if self._is_patch_file(filename) else "source"
        
        properties.append({
            "name": "mock:source:type",
            "value": source_type
        })
        
        # Add signature information if available
        signature = source_file.get("digital_signature")
        if signature:
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
        return lower_name.startswith("patch") or lower_name.endswith(".patch") or lower_name.endswith(".diff")

    def _format_epoch_timestamp(self, epoch_value):
        """Convert epoch timestamp string to ISO8601 if possible."""
        if not epoch_value or epoch_value in ("(none)", "None"):
            return None
        try:
            epoch_int = int(epoch_value)
            if epoch_int <= 0:
                return None
            from datetime import datetime, timezone
            return datetime.fromtimestamp(epoch_int, tz=timezone.utc).isoformat()
        except Exception:
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
            if '/usr/share/man/' in file_path or (file_path.endswith('.gz') and '/man' in file_path):
                return False
        
        return True

    def _create_file_components(self, rpm_path, package_name, package_version):
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
            file_hash = file_data.get("sha256")
            
            bom_ref = self._generate_file_bom_ref(package_name, package_version, file_path)
            component = {
                "type": "file",
                "bom-ref": bom_ref,
                "name": file_path
            }
            
            # Add hash if available
            if file_hash:
                component["hashes"] = [
                    {
                        "alg": "SHA-256",
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
            
            if properties:
                component["properties"] = properties
            
            file_components.append(component)
        
        return file_components

    def _get_source_file_bom_refs(self, package_name, source_files):
        """Gets bom-refs for source files that were used to build a package.
        
        Returns list of bom-refs for source tar.gz and patch files.
        """
        source_bom_refs = []
        
        for source_file in source_files:
            filename = source_file.get("filename", "")
            if not filename:
                continue
            
            # Include source tar.gz files
            if filename.endswith('.tar.gz') or filename.endswith('.tar.bz2') or filename.endswith('.tar.xz'):
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

    def _create_dependency(self, bom_ref, dependencies, component_map, distro):
        """Creates a CycloneDX dependency entry."""
        if not bom_ref:
            return None
        
        # Convert dependency strings to bom-refs
        depends_on = []
        for dep in dependencies:
            # Parse RPM dependency format (e.g., "libc.so.6()(64bit)", "package >= 1.0")
            dep_bom_ref = self._dependency_to_bom_ref(dep, component_map, distro)
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

    def _dependency_to_bom_ref(self, dependency_string, component_map, distro):
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
        
        # Parse signature line like: "RSA/SHA256, Fri 08 Nov 2024 03:56:24 AM EST, Key ID c8ac4916105ef944"
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
        date_match = re.search(r'([A-Za-z]{3} [A-Za-z]{3}\s+\d{1,2} \d{2}:\d{2}:\d{2} \d{4})', signature_string)
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
        
        if sig_type != "unsigned" and sig_type != "unknown":
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
                "value": str(sig_valid)
            })
        
        return properties

    def parse_spec_file(self, spec_path):
        """Parses a spec file to extract source and patch files with their hashes and signatures."""
        print("Parsing spec file")
        if not os.path.isfile(spec_path):
            print(f"Spec file not found: {spec_path}")
            return []
        
        sources = []
        try:
            chroot_spec_path = self._convert_to_chroot_path(spec_path)
            # Use rpmspec --parse inside the build chroot to ensure macro expansion matches the build
            cmd = ["rpmspec", "--parse", chroot_spec_path]
            result, _ = self.buildroot.doChroot(
                cmd, shell=False, returnOutput=True, printOutput=False
            )
            
            for line in (result or "").splitlines():
                line = line.strip()
                # Match lines like Source0: or Patch1:
                match = re.match(r'^(Source|Patch)[0-9]*:\s*(.+)$', line)
                if match:
                    source_file = match.group(2)
                    # Extract hash if present (format: filename#hash)
                    if '#' in source_file:
                        filename, hash_value = source_file.split('#', 1)
                    else:
                        filename = source_file
                        hash_value = None
                    
                    # Extract actual filename from URL if it's a URL
                    if filename.startswith('http'):
                        # Extract filename from URL (last part after /)
                        actual_filename = filename.split('/')[-1]
                    else:
                        actual_filename = filename
                    
                    # Try to find the actual file and calculate its hash
                    build_dir = os.path.dirname(spec_path)
                    # SOURCES directory is at the same level as SPECS, not inside SPECS
                    sources_dir = os.path.join(os.path.dirname(build_dir), "SOURCES")
                    file_path = os.path.join(sources_dir, actual_filename)
                    
                    actual_hash = None
                    if os.path.isfile(file_path):
                        actual_hash = self.hash_file(file_path)
                        print(f"Found source file {actual_filename} at {file_path}, hash: {actual_hash}")
                    elif hash_value:
                        actual_hash = hash_value
                        print(f"Using hash from spec file for {actual_filename}: {hash_value}")
                    else:
                        print(f"Source file {actual_filename} not found at {file_path}")
                    
                    # Check for digital signature (GPG signature)
                    signature = self.get_file_signature(file_path) if os.path.isfile(file_path) else None
                    
                    sources.append({
                        "filename": actual_filename,
                        "sha256": actual_hash,
                        "digital_signature": signature
                    })
            
            print(f"Extracted source and patch files from spec: {sources}")
        except Exception as e:
            print(f"Failed to parse spec file {spec_path}: {e}")
        return sources

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
        except Exception as e:
            print(f"Failed to check signature for {file_path}: {e}")
            return None

    def get_iso_timestamp(self):
        """Returns the current time in ISO 8601 format."""
        from datetime import datetime
        return datetime.utcnow().isoformat() + "Z"

    def get_distribution(self):
        """Returns the distribution name and version from /etc/os-release."""
        try:
            distro = None
            version = None
            if os.path.exists("/etc/os-release"):
                with open("/etc/os-release") as f:
                    for line in f:
                        if line.startswith("NAME="):
                            distro = line.strip().split("=", 1)[1].strip('"')
                        elif line.startswith("VERSION_ID="):
                            version = line.strip().split("=", 1)[1].strip('"')
            if distro and version:
                return f"{distro} {version}"
            elif distro:
                return distro
            else:
                return "Unknown"
        except Exception as e:
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
        
        # Handle special cases for common packages
        if package_name == "glibc":
            vendor = "gnu"
            product = "glibc"
        elif package_name == "openssl":
            vendor = "openssl"
            product = "openssl"
        elif package_name == "gcc":
            vendor = "gnu"
            product = "gcc"
        elif package_name == "make":
            vendor = "gnu"
            product = "make"
        elif package_name == "gettext":
            vendor = "gnu"
            product = "gettext"
        
        # Generate CPE
        cpe = f"cpe:2.3:a:{vendor}:{product}:{version}:*:*:*:*:*:*:*:*"
        return cpe

    def detect_chroot_distribution(self):
        """Detects the distribution name inside the chroot by reading /etc/os-release."""
        try:
            # Use buildroot's doChroot to cat /etc/os-release
            cmd = ["cat", "/etc/os-release"]
            output, _ = self.buildroot.doChroot(cmd, shell=False, returnOutput=True, printOutput=False)
            distro = None
            if output:
                for line in output.splitlines():
                    if line.startswith("ID="):
                        distro = line.strip().split("=", 1)[1].strip('"').lower()
                        break
            if distro:
                return distro
            else:
                return "unknown"
        except Exception as e:
            print(f"Failed to detect chroot distribution: {e}")
            return "unknown"

    def get_build_toolchain_packages(self):
        """Returns the list of packages installed in the build toolchain with detailed signature information."""
        try:
            # First get basic package info
            query = "%{NAME}|%{VERSION}-%{RELEASE}.%{ARCH}|%{LICENSE}|%{BUILDTIME}\n"
            cmd = ["rpm", "-qa", "--qf", query]
            output, _ = self.buildroot.doChroot(cmd, shell=False, returnOutput=True, printOutput=False)
            packages = []
            cpe_vendor_default = self.detect_chroot_distribution() or "unknown"
            import re
            import datetime
            
            for line in output.splitlines():
                parts = line.split("|", 3)
                if len(parts) < 3:
                    continue
                package_name = parts[0].strip()
                package_version = parts[1].strip()
                package_license = parts[2].strip()
                build_time = parts[3].strip() if len(parts) > 3 else None
                
                # Skip GPG keys and other non-package entries
                if package_name.startswith('gpg-pubkey') or package_name == '(none)' or not package_name:
                    continue
                
                # Get detailed signature info for this package
                digital_signature = self.get_package_signature_from_chroot(package_name)
                
                # Build date
                if build_time and build_time.isdigit():
                    try:
                        dt = datetime.datetime.utcfromtimestamp(int(build_time))
                        digital_signature["build_date"] = dt.isoformat() + "Z"
                    except Exception:
                        digital_signature["build_date"] = None
                
                cpe = self.generate_cpe(package_name, package_version, vendor=cpe_vendor_default)
                
                # Get package checksum (SHA-256 of the RPM file)
                package_checksum = self.get_package_checksum_from_chroot(package_name)
                
                packages.append({
                    "name": package_name,
                    "version": package_version,
                    "licenseDeclared": package_license,
                    "digital_signature": digital_signature,
                    "cpe": cpe,
                    "checksum": package_checksum
                })
            print(f"Found {len(packages)} build toolchain packages")
            return packages
        except Exception as e:
            print(f"Failed to get build environment packages: {e}")
            return []

    def get_package_checksum_from_chroot(self, package_name):
        """Gets the SHA-256 checksum of an installed package from inside the chroot."""
        try:
            # Try different RPM header tags to get a checksum
            # SHA256HEADER is the SHA256 checksum of the RPM header
            cmd = ["rpm", "-q", package_name, "--qf", "%{SHA256HEADER}"]
            output, _ = self.buildroot.doChroot(cmd, shell=False, returnOutput=True, printOutput=False)
            
            if output and output.strip() and output.strip() != "(none)" and not output.strip().startswith("error"):
                return output.strip().lower()
            
            # Try SHA1HEADER as fallback (older RPMs)
            cmd = ["rpm", "-q", package_name, "--qf", "%{SHA1HEADER}"]
            output, _ = self.buildroot.doChroot(cmd, shell=False, returnOutput=True, printOutput=False)
            
            if output and output.strip() and output.strip() != "(none)" and not output.strip().startswith("error"):
                # It's SHA-1, but it's better than nothing
                print(f"Warning: Using SHA-1 for {package_name}, SHA-256 not available")
                return output.strip().lower()
            
            # No header checksum available
            print(f"Warning: No checksum available for {package_name}")
            return None
            
        except Exception as e:
            print(f"Failed to get checksum for package {package_name}: {e}")
            return None

    def get_package_signature_from_chroot(self, package_name):
        """Gets detailed signature information for a specific package from inside the chroot."""
        try:
            cmd = ["rpm", "-qi", package_name]
            output, _ = self.buildroot.doChroot(cmd, shell=False, returnOutput=True, printOutput=False)
            
            signature_info = {
                "signature_type": "unsigned",
                "signature_key": None,
                "signature_date": None,
                "signature_algorithm": None,
                "signature_valid": False,
                "raw_signature_data": None,
                "build_date": None
            }
            
            for line in output.splitlines():
                line = line.strip()
                if line.startswith("Signature"):
                    # Extract the signature data after the colon
                    sig_data = line.split(":", 1)[1].strip() if ":" in line else ""
                    signature_info["raw_signature_data"] = sig_data
                    
                    if sig_data and sig_data != "(none)" and sig_data != "":
                        signature_info["signature_type"] = "GPG"
                        signature_info["signature_valid"] = True
                        
                        # Parse signature line like: "RSA/SHA256, Fri 08 Nov 2024 03:56:24 AM EST, Key ID c8ac4916105ef944"
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
                        date_match = re.search(r'([A-Za-z]{3} [A-Za-z]{3}\s+\d{1,2} \d{2}:\d{2}:\d{2} \d{4})', sig_data)
                        if date_match:
                            signature_info["signature_date"] = date_match.group(1)
                    else:
                        signature_info["signature_type"] = "unsigned"
                        signature_info["signature_valid"] = False
                    break
            
            return signature_info
            
        except Exception as e:
            print(f"Failed to get signature for package {package_name}: {e}")
            return {
                "signature_type": "unknown",
                "signature_valid": False,
                "error": str(e)
            }

    def get_package_detailed_signature(self, package_name):
        """Gets detailed signature information for a specific package."""
        try:
            import subprocess
            import shlex
            # Try to use rpm --root to query from outside the chroot first
            # If that fails, fall back to running inside the chroot
            root_path = self.buildroot.rootdir
            cmd = f"rpm --root {shlex.quote(root_path)} -qi {shlex.quote(package_name)}"
            result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            output = result.stdout
            
            # If host rpm command failed (empty output), try running inside chroot
            if not output.strip():
                print(f"Host RPM command failed for {package_name}, trying inside chroot...")
                # Use buildroot's doChroot method to run the command inside the chroot
                cmd = ["rpm", "-qi", package_name]
                output, _ = self.buildroot.doChroot(cmd, shell=False, returnOutput=True, printOutput=False)
                print(f"Chroot RPM output for {package_name}: {output[:200]}...")  # Debug output
            
            signature_info = {
                "signature_type": None,
                "signature_key": None,
                "signature_date": None,
                "signature_algorithm": None,
                "signature_valid": None,
                "raw_signature_data": None,
                "build_date": None
            }
            
            output_lines = output.splitlines()
            i = 0
            signature_found = False
            print(f"DEBUG: Processing {len(output_lines)} lines for package {package_name}")
            while i < len(output_lines):
                line = output_lines[i].strip()
                print(f"DEBUG: Line {i}: '{line}'")
                if line.startswith("Signature"):
                    signature_found = True
                    print(f"DEBUG: Found signature line: '{line}'")
                    # Extract the signature data after the colon
                    sig_data = line.split(":", 1)[1].strip() if ":" in line else ""
                    signature_info["raw_signature_data"] = sig_data
                    print(f"DEBUG: Extracted signature data: '{sig_data}'")
                    
                    if sig_data and sig_data != "(none)" and sig_data != "":
                        signature_info["signature_type"] = "GPG"
                        signature_info["signature_valid"] = True
                        
                        # Parse signature line like: "RSA/SHA256, Fri 08 Nov 2024 03:56:24 AM EST, Key ID c8ac4916105ef944"
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
                        date_match = re.search(r'([A-Za-z]{3} [A-Za-z]{3}\s+\d{1,2} \d{2}:\d{2}:\d{2} \d{4})', sig_data)
                        if date_match:
                            signature_info["signature_date"] = date_match.group(1)
                    else:
                        signature_info["signature_type"] = "unsigned"
                        signature_info["signature_valid"] = False
                    i += 1
                    continue
                
                if line.startswith("Build Date"):
                    # This can help verify the package build time
                    build_date = line.split(":", 1)[1].strip() if ":" in line else None
                    if build_date:
                        signature_info["build_date"] = build_date
                i += 1
            
            # If no signature line was found, mark as unsigned
            if not signature_found:
                signature_info["signature_type"] = "unsigned"
                signature_info["signature_valid"] = False
            
            return signature_info
            
        except Exception as e:
            print(f"Failed to get detailed signature for package {package_name}: {e}")
            return {
                "signature_type": "unknown",
                "signature_valid": False,
                "error": str(e)
            }

    def get_rpm_metadata(self, rpm_path):
        """Extracts metadata from an RPM file."""
        if not os.path.isfile(rpm_path):
            print(f"RPM file not found: {rpm_path}")
            return {}

        # Use individual rpm queries instead of trying to output JSON directly
        try:
            metadata = {}
            
            # Get each field individually
            fields = {
                "name": "%{NAME}",
                "version": "%{VERSION}",
                "release": "%{RELEASE}",
                "arch": "%{ARCH}",
                "epoch": "%{EPOCH}",
                "summary": "%{SUMMARY}",
                "license": "%{LICENSE}",
                "vendor": "%{VENDOR}",
                "url": "%{URL}",
                "packager": "%{PACKAGER}",
                "buildtime": "%{BUILDTIME}",
                "buildhost": "%{BUILDHOST}",
                "sourcerpm": "%{SOURCERPM}",
                "group": "%{GROUP}",
                "distribution": "%{DISTRIBUTION}"
            }
            
            for field_name, field_format in fields.items():
                cmd = ["rpm", "-qp", rpm_path, "--queryformat", field_format]
                result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True)
                value = result.stdout.strip()
                # Handle empty epoch (rpm returns empty string for no epoch)
                if field_name == "epoch" and not value:
                    value = "(none)"
                metadata[field_name] = value
            
            print(f"RPM metadata extracted: {metadata}")
            return metadata
            
        except subprocess.CalledProcessError as e:
            print(f"RPM command failed for {rpm_path}: {e.stderr}")
            return {}
        except Exception as e:
            print(f"Failed to extract RPM metadata: {e}")
            return {}

    def get_rpm_file_list(self, rpm_path):
        """Extracts the list of files from an RPM file."""
        cmd = ["rpm", "-qpl", rpm_path]
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True)
            files = result.stdout.splitlines()
            print(f"Files in RPM {rpm_path}: {files}")
            return files
        except subprocess.CalledProcessError as e:
            print(f"Failed to get file list for {rpm_path}: {e.stderr}")
            return []

    def get_rpm_file_info(self, rpm_path):
        """Extracts file hashes, ownership, and permissions from an RPM file using 'rpm -qp --dump'."""
        cmd = ["rpm", "-qp", "--dump", rpm_path]
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True)
            file_info = {}
            for line in result.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 8:
                    file_path = parts[0]
                    sha256 = parts[3]
                    # If the hash is all zeroes, treat as None
                    if sha256 == "0" * 64 or sha256 == "0000000000000000000000000000000000000000000000000000000000000000":
                        sha256 = None
                    
                    # Parse permissions (field 4), owner (field 5), group (field 6)
                    permissions = parts[4] if len(parts) > 4 else None
                    owner = parts[5] if len(parts) > 5 else None
                    group = parts[6] if len(parts) > 6 else None
                    
                    file_info[file_path] = {
                        "sha256": sha256,
                        "permissions": permissions,
                        "owner": owner,
                        "group": group
                    }
            print(f"File info for RPM {rpm_path}: {file_info}")
            return file_info
        except subprocess.CalledProcessError as e:
            print(f"Failed to get file info for {rpm_path}: {e.stderr}")
            return {}

    def get_rpm_dependencies(self, rpm_path):
        """Extracts the list of dependencies from an RPM file."""
        cmd = ["rpm", "-qpR", rpm_path]
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True)
            dependencies = result.stdout.splitlines()
            print(f"Dependencies for RPM {rpm_path}: {dependencies}")
            return dependencies
        except subprocess.CalledProcessError as e:
            print(f"Failed to get dependencies for {rpm_path}: {e.stderr}")
            return []

    def get_rpm_signature(self, rpm_path):
        """Extracts the GPG signature of an RPM file."""
        cmd = ["rpm", "-qpi", rpm_path]
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True)
            for line in result.stdout.splitlines():
                if line.startswith("Signature"):
                    # Extract the signature data after the colon
                    sig_data = line.split(":", 1)[1].strip() if ":" in line else ""
                    print(f"GPG Signature for {rpm_path}: {sig_data}")
                    return sig_data
            return None
        except subprocess.CalledProcessError as e:
            print(f"Failed to get GPG signature for {rpm_path}: {e.stderr}")
            return None

    def hash_file(self, file_path):
        """Calculates the SHA256 hash of a file."""
        sha256 = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except Exception as e:
            print(f"Failed to hash file {file_path}: {e}")
            return None

    def extract_source_files_from_srpm(self, src_rpm_path):
        """Extracts source files from a source RPM."""
        print(f"Extracting source files from source RPM: {src_rpm_path}")
        source_files = []
        try:
            temp_dir = tempfile.mkdtemp(prefix="sbom-srpm-")
            try:
                extract_cmd = f"rpm2cpio {shlex.quote(src_rpm_path)} | cpio -idm 2>/dev/null"
                subprocess.run(extract_cmd, shell=True, cwd=temp_dir, check=True)
            except subprocess.CalledProcessError as e:
                print(f"Failed to unpack source RPM {src_rpm_path}: {e}")
                shutil.rmtree(temp_dir, ignore_errors=True)
                return source_files
            
            for root_dir, _, files in os.walk(temp_dir):
                for file_name in files:
                    if file_name.endswith(".spec"):
                        continue
                    file_path = os.path.join(root_dir, file_name)
                    sha256 = self.hash_file(file_path)
                    signature = self.get_file_signature(file_path)
                    source_files.append({
                        "filename": file_name,
                        "sha256": sha256,
                        "digital_signature": signature
                    })
            try:
                shutil.rmtree(temp_dir)
            except Exception:
                pass
                
            print(f"Extracted source files from source RPM: {source_files}")
        except Exception as e:
            print(f"Failed to extract source files from source RPM {src_rpm_path}: {e}")
        
        return source_files

    def _convert_to_chroot_path(self, host_path):
        """Convert an absolute host path into the corresponding path inside the build chroot."""
        rootdir = getattr(self.buildroot, "rootdir", "")
        if not rootdir:
            return host_path
        if host_path.startswith(rootdir):
            rel_path = host_path[len(rootdir):]
            if not rel_path.startswith("/"):
                rel_path = "/" + rel_path
            return rel_path
        return host_path
