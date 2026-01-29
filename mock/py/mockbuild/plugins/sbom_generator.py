# -*- coding: utf-8 -*-
# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# License: GPL2 or later see COPYING
# Written by Scott R. Shinn <scott@atomicorp.com>
# Copyright (C) 2025, Atomicorp, Inc.
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
    if "type" in opts and opts["type"] != "cyclonedx":
        # We only support cyclonedx for now
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
        self.sbom_done = False

        # Configuration options for file-level dependencies and filtering
        self.include_file_dependencies = self.conf.get('include_file_dependencies', False)
        self.include_file_components = self.conf.get('include_file_components', True)
        self.include_debug_files = self.conf.get('include_debug_files', False)
        self.include_man_pages = self.conf.get('include_man_pages', True)
        self.include_source_dependencies = self.conf.get('include_source_dependencies', True)
        self.include_toolchain_dependencies = self.conf.get('include_toolchain_dependencies', False)

        plugins.add_hook("prebuild", self._list_specs_directory)
        plugins.add_hook("postbuild", self._generate_sbom_post_build_hook)

    @traceLog()
    def _list_specs_directory(self):
        """Lists the contents of the SPECS directory before building."""

        self.buildroot.root_log.debug("DEBUG: Listing contents of SPECS directory before building:")
        self.buildroot.root_log.debug(f"DEBUG: builddir is {self.buildroot.builddir}")
        self.buildroot.root_log.debug(f"DEBUG: rootdir is {self.rootdir}")
        self.buildroot.root_log.debug(f"DEBUG: resultsdir is {self.buildroot.resultdir}")

        # Look for spec file in the build directory
        build_dir = self.buildroot.builddir
        specs_dir = os.path.join(build_dir, "SPECS")
        self.buildroot.root_log.debug(f"DEBUG: spec dir is {specs_dir}")

        try:
            if os.path.exists(specs_dir):
                specs_files = os.listdir(specs_dir)
                self.buildroot.root_log.debug(f"Contents of SPECS directory: {specs_files}")
            else:
                self.buildroot.root_log.debug("SPECS directory does not exist.")
        except OSError as e:
            self.buildroot.root_log.debug(f"Failed to list contents of SPECS directory: {e}")

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

        if spec_file:
            build_subject_name = os.path.splitext(os.path.basename(spec_file))[0]
            parsed_sources = self.parse_spec_file(spec_file)
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
                # Extract from source RPM if available
                source_files = self.extract_source_files_from_srpm(srpm_path)

        return (
            build_subject_name, build_subject_version,
            build_subject_release, source_files
        )

    def _add_source_components(self, bom, source_files):
        """Converts source files to CycloneDX components and returns metadata entries."""
        source_component_entries = []
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
        return source_component_entries

    def _add_toolchain_components(self, bom, build_toolchain_packages, distro_id):
        """Adds toolchain components to the BOM and returns their bom-refs."""
        toolchain_bom_refs = []
        for toolchain_pkg in build_toolchain_packages:
            component = self._create_toolchain_component(toolchain_pkg, distro_id)
            if component:
                bom_ref = component.get("bom-ref")
                if bom_ref:
                    toolchain_bom_refs.append(bom_ref)
                bom["components"].append(component)
        return toolchain_bom_refs

    @traceLog()
    # pylint: disable=too-many-locals
    def _generate_sbom_post_build_hook(self):
        """Plugin hook called after the build is complete."""
        if self.sbom_done or not self.sbom_enabled:
            return

        state_text = "Generating CycloneDX SBOM for built packages v1.0"
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
                build_subject_name, build_subject_version,
                build_subject_release, source_files
            ) = self._get_build_subject_metadata(spec_file, src_rpm_files, build_dir)

            # Construct output filename using package name-version-release format
            if not build_subject_name or not build_subject_version or not build_subject_release:
                self.buildroot.root_log.debug("Cannot generate SBOM - build metadata incomplete")
                return

            sbom_filename = (
                f"{build_subject_name}-{build_subject_version}-{build_subject_release}.sbom"
            )
            out_file = os.path.join(self.buildroot.resultdir, sbom_filename)

            # Create CycloneDX document
            bom = self._create_cyclonedx_document()
            build_toolchain_packages = self.get_build_toolchain_packages()

            # Add source and toolchain components
            source_component_entries = self._add_source_components(bom, source_files)
            distro_id = self.detect_chroot_distribution() or "fedora"
            toolchain_bom_refs = self._add_toolchain_components(
                bom, build_toolchain_packages, distro_id
            )

            # Process binary RPMs and convert to components
            (
                built_package_bom_refs, primary_rpm_metadata
            ) = self._process_built_packages(
                bom, rpm_files, build_dir, distro_id, source_component_entries,
                build_subject_name, build_toolchain_packages, toolchain_bom_refs
            )

            # Add RPM-specific metadata and finalize dependencies
            self._finalize_bom_metadata(bom, primary_rpm_metadata, built_package_bom_refs,
                                        build_subject_name, build_subject_version,
                                        build_subject_release, distro_id)
            self._finalize_dependencies(bom, source_component_entries,
                                        build_toolchain_packages, distro_id)

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
        """Processes binary RPMs and creates CycloneDX components and dependencies."""
        built_package_bom_refs = []
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
                file_components = self._create_file_components(
                    rpm_path, package_name, package_version
                )
                for file_comp in file_components:
                    bom["components"].append(file_comp)
                    if self._should_include_file_dependency(file_comp.get("name", "")):
                        bom["dependencies"].append({
                            "ref": file_comp["bom-ref"],
                            "dependsOn": [bom_ref]
                        })

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

            all_depends_on = list(set(all_depends_on))
            if all_depends_on:
                bom["dependencies"].append({"ref": bom_ref, "dependsOn": all_depends_on})
            elif runtime_dependency:
                bom["dependencies"].append(runtime_dependency)

        return built_package_bom_refs, primary_rpm_metadata

    # pylint: disable=too-many-arguments,too-many-locals,too-many-branches,too-many-statements,too-many-positional-arguments
    def _finalize_bom_metadata(self, bom, primary_rpm_metadata, built_package_bom_refs,
                              build_subject_name, build_subject_version,
                              build_subject_release, distro_id):
        """Adds RPM-specific metadata and component information to the BOM."""
        if primary_rpm_metadata:
            rpm_props = bom["metadata"]["properties"]
            for key, prop_name in [("buildhost", "mock:rpm:buildhost"),
                                  ("buildtime", "mock:rpm:buildtime"),
                                  ("sourcerpm", "mock:rpm:sourcerpm"),
                                  ("group", "mock:rpm:group"),
                                  ("epoch", "mock:rpm:epoch"),
                                  ("distribution", "mock:rpm:distribution")]:
                val = primary_rpm_metadata.get(key)
                if val and val != "(none)" and (key != "epoch" or val.strip()):
                    rpm_props.append({"name": prop_name, "value": val})

            vendor = primary_rpm_metadata.get("vendor")
            if vendor and vendor != "(none)":
                bom["metadata"]["manufacture"] = {"name": vendor}
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
                    if aggregate_name and aggregate_version:
                        component_obj["purl"] = self._generate_purl(
                            aggregate_name, aggregate_version, distro_id
                        )
                    bom["metadata"]["component"] = component_obj

    # pylint: disable=too-many-locals,too-many-branches,too-many-statements
    def _finalize_dependencies(self, bom, source_component_entries,
                              build_toolchain_packages, distro_id):
        """Ensures every component has a dependency entry."""
        dependencies_dict = {dep.get("ref"): dep for dep in bom["dependencies"] if dep.get("ref")}

        for source_entry in source_component_entries:
            ref = source_entry.get("bom_ref")
            if ref and ref not in dependencies_dict:
                dependencies_dict[ref] = {"ref": ref, "dependsOn": []}

        for toolchain_pkg in build_toolchain_packages:
            name, ver = toolchain_pkg.get("name"), toolchain_pkg.get("version")
            if name and ver:
                purl = self._generate_purl(name, ver, distro_id)
                if purl and purl not in dependencies_dict:
                    dependencies_dict[purl] = {"ref": purl, "dependsOn": []}

        for component in bom["components"]:
            ref = component.get("bom-ref")
            if ref and ref not in dependencies_dict:
                dependencies_dict[ref] = {"ref": ref, "dependsOn": []}

        bom["dependencies"] = list(dependencies_dict.values())


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
                    "expression": license_str
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
                "value": str(sig_valid)
            })

        return properties

    def parse_spec_file(self, spec_path):
        """Parses a spec file to extract source and patch files with their hashes and signatures."""
        self.buildroot.root_log.debug("Parsing spec file")
        if not os.path.isfile(spec_path):
            self.buildroot.root_log.debug(f"Spec file not found: {spec_path}")
            return []

        sources = []
        try:
            chroot_spec_path = self.from_chroot_path(spec_path)
            # Use rpmspec --parse inside the build chroot to insure macro expansion
            # matches the build
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
                        self.buildroot.root_log.debug(
                            f"Found source file {actual_filename} at {file_path}, "
                            f"hash: {actual_hash}"
                        )
                    elif hash_value:
                        actual_hash = hash_value
                        self.buildroot.root_log.debug(
                            f"Using hash from spec file for {actual_filename}: {hash_value}"
                        )
                    else:
                        self.buildroot.root_log.debug(
                            f"Source file {actual_filename} not found at {file_path}"
                        )

                    # Check for digital signature (GPG signature)
                    signature = (
                        self.get_file_signature(file_path) if os.path.isfile(file_path) else None
                    )

                    sources.append({
                        "filename": actual_filename,
                        "sha256": actual_hash,
                        "digital_signature": signature
                    })

            self.buildroot.root_log.debug(f"Extracted source and patch files from spec: {sources}")
        # pylint: disable=broad-exception-caught
        except Exception as e:
            self.buildroot.root_log.debug(f"Failed to parse spec file {spec_path}: {e}")
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
            # Query the chroot filesystem directly using root_dir parameter
            # pylint: disable=unexpected-keyword-arg
            distro_id = distro.id(root_dir=self.buildroot.rootdir)
            if distro_id:
                return distro_id.lower()
            return "unknown"
        # pylint: disable=broad-exception-caught
        except Exception as e:
            self.buildroot.root_log.debug(f"Failed to detect chroot distribution: {e}")
            return "unknown"

    def get_build_toolchain_packages(self):
        """Returns the list of packages installed in the build toolchain
        with detailed signature information."""
        try:
            # First get basic package info
            query = "%{NAME}|%{VERSION}-%{RELEASE}.%{ARCH}|%{LICENSE}|%{BUILDTIME}\n"
            cmd = ["rpm", "-qa", "--qf", query]
            output, _ = self.buildroot.doChroot(
                cmd, shell=False, returnOutput=True, printOutput=False
            )
            packages = []
            cpe_vendor_default = self.detect_chroot_distribution() or "unknown"

            for line in output.splitlines():
                parts = line.split("|", 3)
                if len(parts) < 3:
                    continue
                package_name = parts[0].strip()
                package_version = parts[1].strip()
                package_license = parts[2].strip()
                build_time = parts[3].strip() if len(parts) > 3 else None

                # Skip GPG keys and other non-package entries
                if (
                    package_name.startswith('gpg-pubkey') or
                    package_name == '(none)' or
                    not package_name
                ):
                    continue

                # Get detailed signature info for this package
                digital_signature = self.get_package_signature_from_chroot(package_name)

                # Build date
                if build_time and build_time.isdigit():
                    try:
                        dt = datetime.fromtimestamp(int(build_time), tz=timezone.utc)
                        digital_signature["build_date"] = dt.isoformat()
                    except (ValueError, TypeError, OverflowError):
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
            self.buildroot.root_log.debug(f"Found {len(packages)} build toolchain packages")
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

    def get_package_signature_from_chroot(self, package_name):
        """Gets detailed signature information for a specific package from inside the chroot."""
        try:
            cmd = ["rpm", "-qi", package_name]
            output, _ = self.buildroot.doChroot(
                cmd, shell=False, returnOutput=True, printOutput=False
            )

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
                    self._parse_signature_data(sig_data, signature_info)
                    break

            return signature_info

        # pylint: disable=broad-exception-caught
        except Exception as e:
            self.buildroot.root_log.debug(
                f"Failed to get signature for package {package_name}: {e}"
            )
            return {
                "signature_type": "unknown",
                "signature_valid": False,
                "error": str(e)
            }

    def get_package_detailed_signature(self, package_name):
        """Gets detailed signature information for a specific package."""
        try:
            # Try to use rpm --root to query from outside the chroot first
            # If that fails, fall back to running inside the chroot
            root_path = self.buildroot.rootdir
            cmd = f"rpm --root {shlex.quote(root_path)} -qi {shlex.quote(package_name)}"
            result = subprocess.run(
                cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, check=False
            )
            output = result.stdout

            # If host rpm command failed (empty output), try running inside chroot
            if not output.strip():
                self.buildroot.root_log.debug(
                    f"Host RPM command failed for {package_name}, trying inside chroot..."
                )
                # Use buildroot's doChroot method to run the command inside the chroot
                cmd = ["rpm", "-qi", package_name]
                output, _ = self.buildroot.doChroot(
                    cmd, shell=False, returnOutput=True, printOutput=False
                )
                self.buildroot.root_log.debug(
                    f"Chroot RPM output for {package_name}: {output[:200]}..."
                )  # Debug output

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
            self.buildroot.root_log.debug(
                f"DEBUG: Processing {len(output_lines)} lines for package {package_name}"
            )
            while i < len(output_lines):
                line = output_lines[i].strip()
                self.buildroot.root_log.debug(f"DEBUG: Line {i}: '{line}'")
                if line.startswith("Signature"):
                    signature_found = True
                    self.buildroot.root_log.debug(f"DEBUG: Found signature line: '{line}'")
                    # Extract the signature data after the colon
                    sig_data = line.split(":", 1)[1].strip() if ":" in line else ""
                    signature_info["raw_signature_data"] = sig_data
                    self.buildroot.root_log.debug(f"DEBUG: Extracted signature data: '{sig_data}'")
                    self._parse_signature_data(sig_data, signature_info)
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

        # pylint: disable=broad-exception-caught
        except Exception as e:
            self.buildroot.root_log.debug(
                f"Failed to get detailed signature for package {package_name}: {e}"
            )
            return {
                "signature_type": "unknown",
                "signature_valid": False,
                "error": str(e)
            }

    def get_rpm_metadata(self, rpm_path):
        """Extracts metadata from an RPM file."""
        if not os.path.isfile(rpm_path):
            self.buildroot.root_log.debug(f"RPM file not found: {rpm_path}")
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
                result = subprocess.run(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True
                )
                value = result.stdout.strip()
                # Handle empty epoch (rpm returns empty string for no epoch)
                if field_name == "epoch" and not value:
                    value = "(none)"
                metadata[field_name] = value

            self.buildroot.root_log.debug(f"RPM metadata extracted: {metadata}")
            return metadata

        except subprocess.CalledProcessError as e:
            self.buildroot.root_log.debug(f"RPM command failed for {rpm_path}: {e.stderr}")
            return {}
        # pylint: disable=broad-exception-caught
        except Exception as e:
            self.buildroot.root_log.debug(f"Failed to extract RPM metadata: {e}")
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
                # Format permissions as octal string (e.g., 0100755) to match rpm --dump format
                permissions = f"0{mode:o}"

                owner = fileusernames[i]
                if isinstance(owner, bytes):
                    owner = owner.decode('utf-8', 'replace')

                group = filegroupnames[i]
                if isinstance(group, bytes):
                    group = group.decode('utf-8', 'replace')

                file_info[filename] = {
                    "sha256": digest,
                    "permissions": permissions,
                    "owner": owner,
                    "group": group
                }

            self.buildroot.root_log.debug(
                f"File info for RPM {rpm_path}: {len(file_info)} files processed"
            )
            return file_info

        # pylint: disable=broad-exception-caught
        except Exception as e:
            self.buildroot.root_log.debug(f"Failed to get file info for {rpm_path}: {e}")
            self.buildroot.root_log.debug(traceback.format_exc())
            return {}

    def get_rpm_dependencies(self, rpm_path):
        """Extracts the list of dependencies from an RPM file."""
        cmd = ["rpm", "-qpR", rpm_path]
        try:
            result = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True
            )
            dependencies = result.stdout.splitlines()
            self.buildroot.root_log.debug(f"Dependencies for RPM {rpm_path}: {dependencies}")
            return dependencies
        except subprocess.CalledProcessError as e:
            self.buildroot.root_log.debug(f"Failed to get dependencies for {rpm_path}: {e.stderr}")
            return []

    def get_rpm_signature(self, rpm_path):
        """Extracts the GPG signature of an RPM file."""
        cmd = ["rpm", "-qpi", rpm_path]
        try:
            result = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True
            )
            for line in result.stdout.splitlines():
                if line.startswith("Signature"):
                    # Extract the signature data after the colon
                    sig_data = line.split(":", 1)[1].strip() if ":" in line else ""
                    self.buildroot.root_log.debug(f"GPG Signature for {rpm_path}: {sig_data}")
                    return sig_data
            return None
        except subprocess.CalledProcessError as e:
            self.buildroot.root_log.debug(f"Failed to get GPG signature for {rpm_path}: {e.stderr}")
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
        """Extracts source files from a source RPM."""

        self.buildroot.root_log.debug(f"Extracting source files from source RPM: {src_rpm_path}")
        source_files = []
        try:
            temp_dir = tempfile.mkdtemp(prefix="sbom-srpm-")
            try:
                # Use rpm2archive instead of rpm2cpio to handle large files (>4GB)
                # rpm2archive creates a .tgz file in the current directory
                extract_cmd = ["rpm2archive", src_rpm_path]
                subprocess.run(
                    extract_cmd, cwd=temp_dir, check=True, stderr=subprocess.PIPE, text=True
                )

                # Find the generated archive (should be only one file ending in .tgz or .tar.gz)
                archive_file = None
                for f in os.listdir(temp_dir):
                    if f.endswith(".tgz") or f.endswith(".tar.gz"):
                        archive_file = os.path.join(temp_dir, f)
                        break

                if archive_file:
                    tar_cmd = ["tar", "-xf", archive_file]
                    subprocess.run(tar_cmd, cwd=temp_dir, check=True)
                    os.remove(archive_file)
                else:
                    self.buildroot.root_log.debug(
                        f"rpm2archive did not produce expected output for {src_rpm_path}"
                    )

            except (subprocess.CalledProcessError, OSError) as e:
                self.buildroot.root_log.debug(f"Failed to unpack source RPM {src_rpm_path}: {e}")
                mockbuild.file_util.rmtree(temp_dir)
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
                mockbuild.file_util.rmtree(temp_dir)
            except OSError:
                pass

            print(f"Extracted source files from source RPM: {source_files}")
        # pylint: disable=broad-exception-caught
        except Exception as e:
            print(f"Failed to extract source files from source RPM {src_rpm_path}: {e}")

        return source_files

    def from_chroot_path(self, host_path):
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
