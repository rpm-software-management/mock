# -*- coding: utf-8 -*-
# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# License: GPL2 or later see COPYING
# Written by Scott R. Shinn <scott@atomicorp.com>
# Copyright (C) 2026, Atomicorp, Inc.
"""Mock plugin for generating CycloneDX SBOMs from built RPM packages."""

from mockbuild.plugins.sbom_utils import RpmQueryHelper
from mockbuild.plugins.sbom_spdx import SpdxGenerator
from mockbuild.plugins.sbom_cyclonedx import CycloneDxGenerator
import os
import json
import subprocess
import socket
import traceback
from datetime import datetime, timezone





from mockbuild.trace_decorator import traceLog

# pylint: disable=invalid-name
requires_api_version = "1.1"  # Ensure compatibility with mock API
# pylint: enable=invalid-name

# Plugin entry point
@traceLog()
def init(plugins, conf, buildroot):
    """Initializes the SBOM generator plugin."""
    # Ensure configuration exists for the plugin
    if "type" in conf and conf["type"] not in ("cyclonedx", "spdx"):
        # We only support cyclonedx and spdx for now
        buildroot.root_log.warning(
            f"SBOM generator type '{conf['type']}' not supported, defaulting to 'cyclonedx'"
        )
        conf["type"] = "cyclonedx"

    SBOMGenerator(plugins, conf, buildroot)

class SBOMGenerator:
    """Generates SBOM for the built packages."""
    # pylint: disable=too-few-public-methods,too-many-instance-attributes
    @traceLog()
    def __init__(self, plugins, conf, buildroot):

        self.buildroot = buildroot
        self.conf = conf
        self.rpm_helper = RpmQueryHelper(self.buildroot)
        self.spdx_gen = SpdxGenerator(self.rpm_helper, self.buildroot, conf=self.conf)
        self.cdx_gen = CycloneDxGenerator(self.rpm_helper, self.buildroot, conf=self.conf)
        self.state = buildroot.state
        self.rootdir = buildroot.rootdir
        self.builddir = buildroot.builddir
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
                        metadata, sources = self.rpm_helper.parse_spec_file(spec_file)
                        self.prebuild_spec_metadata = metadata
                        self.prebuild_source_files = sources
                        break
            else:
                self.buildroot.root_log.debug("SPECS directory does not exist for pre-build capture.")
        except Exception as e:
            self.buildroot.root_log.debug(f"Failed to capture pre-build state: {e}")

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

        distro_name = self.rpm_helper.get_distribution()
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
            spec_metadata, parsed_sources = self.rpm_helper.parse_spec_file(spec_file)
            if spec_metadata:
                build_subject_name = spec_metadata.get("name")
                build_subject_version = spec_metadata.get("version")
                build_subject_release = spec_metadata.get("release")
            if parsed_sources:
                source_files = parsed_sources

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

            if not source_files:
                # Extract metadata for source files from source RPM without full extraction
                source_files = self.rpm_helper.extract_source_files_from_srpm(srpm_path)

            # Record the source RPM itself as an input artifact
            srpm_name = src_rpm_files[0]
            srpm_sig = self.rpm_helper.get_rpm_signature(srpm_path)
            srpm_hash = self.rpm_helper.hash_file(srpm_path)
            # Add to the beginning of the list for visibility
            source_files.insert(0, {
                "filename": srpm_name,
                "sha256": srpm_hash,
                "digital_signature": srpm_sig,
                "source_type": "source_rpm"
            })

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

    @traceLog()
    # pylint: disable=too-many-locals
    def _generate_sbom_post_build_hook(self):
        """Plugin hook called after the build is complete."""
        self.buildroot.root_log.debug("[SBOM] Starting post-build SBOM generation")
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
                self.buildroot.root_log.debug("[SBOM] Cannot generate SBOM - build metadata incomplete")
                return

            # Gather common data
            distro_id = self.rpm_helper.detect_chroot_distribution() or "unknown"
            build_toolchain_packages = self.rpm_helper.get_build_toolchain_packages()

            # Dispatch based on type
            if self.sbom_type == "spdx":
                sbom_filename = (
                    f"{build_subject_name}-{build_subject_version}-{build_subject_release}.spdx.json"
                )
                out_file = os.path.join(self.buildroot.resultdir, sbom_filename)

                # Collect hardening flags
                hardening_props = self._collect_build_hardening_properties()

                doc = self.spdx_gen.generate_spdx_document(
                    build_subject_name, build_subject_version, build_subject_release,
                    build_dir, rpm_files, source_files,
                    build_toolchain_packages, distro_id,
                    spec_metadata=spec_metadata, hardening_props=hardening_props
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
                bom = self.cdx_gen.create_cyclonedx_document()

                # Add source and toolchain components
                source_components, source_component_entries = self.cdx_gen.add_source_components(bom, source_files)
                toolchain_components, toolchain_bom_refs = self._add_toolchain_components(
                    bom, build_toolchain_packages, distro_id
                )

                # Process binary RPMs and convert to components
                (
                    built_package_bom_refs, primary_rpm_metadata, all_built_components
                ) = self.cdx_gen.process_built_packages(
                    bom, rpm_files + src_rpm_files, build_dir, distro_id, source_component_entries,
                    build_subject_name, build_toolchain_packages, toolchain_bom_refs
                )

                # Add RPM-specific metadata and finalize dependencies
                self.cdx_gen.finalize_bom_metadata(bom, primary_rpm_metadata, built_package_bom_refs,
                                            build_subject_name, build_subject_version,
                                            build_subject_release, distro_id,
                                            spec_metadata=spec_metadata)
                self.cdx_gen.finalize_dependencies(bom, source_component_entries,
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
            self.buildroot.root_log.debug(f"[SBOM] FAILED: An error occurred during SBOM generation: {e}")
            traceback.print_exc()
        finally:
            self.sbom_done = True
            self.state.finish(state_text)

    # pylint: disable=too-many-arguments,too-many-locals,too-many-branches,too-many-statements,too-many-positional-arguments
    def _create_built_package_component(
        self, rpm_path, distro_obj, _source_components=None
    ):
        """Creates a CycloneDX component for a built RPM package."""
        package_data = self.rpm_helper.get_rpm_metadata(rpm_path)
        if not package_data:
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
        cpe = self.rpm_helper.generate_cpe(package_name, version, vendor=vendor)
        if cpe:
            component["externalReferences"] = [
                {
                    "type": "other",
                    "comment": "CPE 2.3",
                    "url": cpe
                }
            ]

        # Add hierarchical grouping for "RPM Contents"

        # Add hash of RPM file - REMOVED per user request to only have hashes for files contained in RPM
        # or if needed for PURL integrity, but we'll prioritize the "only" constraint.
        # rpm_hash = package_data.get("sha256")
        # if not rpm_hash or rpm_hash == "(none)":
        #     rpm_hash = self.rpm_helper.hash_file(rpm_path)
        
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

        buildtime_iso = self.cdx_gen.format_epoch_timestamp(package_data.get("buildtime"))
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
        signature = self.rpm_helper.get_rpm_signature(rpm_path)
        if signature:
            # Parse signature info
            sig_props = self.cdx_gen.parse_signature_to_properties(signature)
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


