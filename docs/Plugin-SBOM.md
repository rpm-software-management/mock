---
layout: default
title: Plugin SBOM Generator
---

This plugin generates a Software Bill of Materials (SBOM) in CycloneDX format for packages built with Mock. The SBOM provides detailed information about the build environment, source files, and resulting packages, optimized for security use cases.

## Features

* Generates SBOM in CycloneDX 1.5 format (JSON)
* Captures information about:
  * Source files and patches from spec files
  * Binary RPM metadata with PURL and CPE identifiers
  * Complete build toolchain packages
  * Runtime dependencies
  * File hashes (SHA-256)
  * GPG signatures with detailed metadata
* Outputs SBOM as JSON file in the build results directory
* Compatible with security scanners (Grype, Trivy, Snyk)

## Usage

### Basic Usage

The simplest way to use the SBOM generator is to enable it for a single build:

```bash
# Build a package and generate SBOM
mock --enable-plugin=sbom_generator --rebuild package.src.rpm

# Or build from an existing SRPM
mock --enable-plugin=sbom_generator --rebuild ~/rpmbuild/SRPMS/package-1.0-1.fc42.src.rpm

# Specify a chroot configuration
mock --enable-plugin=sbom_generator --rebuild package.src.rpm -r rocky-9-x86_64
```

After the build completes, the SBOM will be available in the build results directory:

```bash
# Find the SBOM file
ls /var/lib/mock/*/result/sbom.cyclonedx.json

# View the SBOM
cat /var/lib/mock/rocky-9-x86_64/result/sbom.cyclonedx.json | jq .

# Get build results directory path
mock --resultdir package.src.rpm
```

### Viewing and Analyzing the SBOM

The generated SBOM can be analyzed using various tools:

```bash
# View basic SBOM information
jq '.metadata.component' sbom.cyclonedx.json
jq '.components | length' sbom.cyclonedx.json
jq '.dependencies | length' sbom.cyclonedx.json

# List all built packages
jq '.components[] | select(.type == "library") | {name, version, purl}' sbom.cyclonedx.json

# List source files used in the build
jq '.components[] | select(.properties[]?.name == "mock:source:type") | {name, hashes}' sbom.cyclonedx.json

# View runtime dependencies for a specific package
jq '.dependencies[] | select(.ref | contains("httpd"))' sbom.cyclonedx.json
```

### Using with Security Scanners

The SBOM can be directly used with security vulnerability scanners:

```bash
# Scan with Grype
grype sbom:./sbom.cyclonedx.json

# Scan with Trivy
trivy sbom sbom.cyclonedx.json

# Export to other formats if needed
syft convert sbom.cyclonedx.json -o spdx-json > sbom.spdx.json
```

## Configuration

### Enabling the Plugin

The plugin is disabled by default. You can enable it in several ways:

**Option 1: Command line (recommended for one-off builds)**
```bash
mock --enable-plugin=sbom_generator --rebuild package.src.rpm
```

**Option 2: Configuration file (for persistent enablement)**

Add to your Mock configuration file (e.g., `/etc/mock/fedora-rawhide-x86_64.cfg`):

```python
config_opts['plugin_conf']['sbom_generator_enable'] = True
config_opts['plugin_conf']['sbom_generator_opts'] = {
    'generate_sbom': True
}
```

**Option 3: User configuration**

Add to `~/.config/mock/mock.cfg`:

```python
config_opts['plugin_conf']['sbom_generator_enable'] = True
```

### Configuration Options

The plugin supports several configuration options to control SBOM generation:

```python
config_opts['plugin_conf']['sbom_generator_opts'] = {
    'generate_sbom': True,              # Enable SBOM generation (default: True)
    'include_file_components': True,    # Include file-level components (default: True)
    'include_file_dependencies': True,  # Include file-to-package dependencies (default: True)
    'include_debug_files': False,       # Include debug files in file components (default: False)
    'include_man_pages': False,         # Include man pages in file components (default: False)
    'include_toolchain_dependencies': False,  # Include build toolchain in dependencies (default: False)
}
```

**Configuration Options Explained:**

- `include_file_components`: When enabled, creates individual file components for each file in built packages, including hashes, permissions, and ownership information.
- `include_file_dependencies`: Creates dependency relationships showing which files belong to which packages.
- `include_debug_files`: Filters out debug files (`.debug`, files in `/usr/lib/debug`) from file components.
- `include_man_pages`: Filters out man pages from file components.
- `include_toolchain_dependencies`: Adds build toolchain packages to the dependencies array (useful for complete build provenance, but can make dependency graphs very large).

## Output

The plugin generates a file named `sbom.cyclonedx.json` in the build results directory (typically `/var/lib/mock/fedora-42-x86_64/result/`). The SBOM includes:

* CycloneDX document metadata
  * Build timestamp
  * Tool information (Mock SBOM Generator)
  * Mock-specific build properties (host, distribution, chroot, config)
  * RPM header metadata surfaced at the document level (buildhost, buildtime, source RPM, group, epoch, distribution, manufacture/vendor)
* Components array containing:
  * Built packages (type: "library" or "application")
    * Package name, version, and PURL
    * CPE identifiers for vulnerability matching
    * License information plus RPM summary as description
    * RPM file SHA-256 hash
    * Vendor, packager, buildhost, buildtime, source RPM, group, epoch, distribution metadata
    * Upstream/project URLs and source RPM links via `externalReferences`
    * GPG signature details
    * Note: Source tarballs and patches are represented as separate file components in the components array with their own BOM refs for traceability
  * Build toolchain packages (type: "library")
    * All packages installed in the build environment
    * Signature information
    * Marked with `mock:role: "build-toolchain"` property
  * Source files (type: "file")
    * Source and patch files from spec
    * SHA-256 hashes
    * Signature information if available
* Dependencies array
  * Runtime dependencies for built packages (libraries/RPMs the package depends on)
  * Dependency relationships modeled using bom-refs
  * Note: Source code relationships are represented in component properties and the components array, not in the dependencies section (source code is a build input, not a runtime dependency)

## Example SBOM Structure

```json
{
  "bomFormat": "CycloneDX",
  "specVersion": "1.5",
  "serialNumber": "urn:uuid:...",
  "version": 1,
  "metadata": {
    "timestamp": "2024-01-19T15:20:00Z",
    "tools": [
      {
        "vendor": "Mock",
        "name": "mock-sbom-generator",
        "version": "1.0"
      }
    ],
    "properties": [
      { "name": "mock:build:host", "value": "build.example.com" },
      { "name": "mock:build:distribution", "value": "Fedora 42" },
      { "name": "mock:build:chroot", "value": "/var/lib/mock/fedora-42-x86_64/root" },
      { "name": "mock:rpm:buildhost", "value": "builder.fedora.example.org" },
      { "name": "mock:rpm:buildtime", "value": "2024-01-19T15:15:00+00:00" },
      { "name": "mock:rpm:sourcerpm", "value": "package-name-1.0-1.fc42.src.rpm" },
      { "name": "mock:rpm:group", "value": "System Environment/Libraries" },
      { "name": "mock:rpm:epoch", "value": "1" }
    ],
    "manufacture": {
      "name": "Fedora Project"
    },
    "component": {
      "type": "application",
      "name": "package-name",
      "version": "1.0-1.fc42",
      "bom-ref": "build-output:package-name",
      "description": "Package summary (build output containing 3 package(s))",
      "licenses": [
        {
          "license": {
            "id": "MIT"
          }
        }
      ],
      "externalReferences": [
        { "type": "distribution", "url": "package-name-1.0-1.fc42.src.rpm" },
        { "type": "website", "url": "https://example.com/package-name" }
      ]
    }
  },
  "components": [
    {
      "type": "library",
      "bom-ref": "pkg:rpm/fedora/package-name@1.0-1.fc42?arch=x86_64",
      "name": "package-name",
      "version": "1.0-1.fc42",
      "purl": "pkg:rpm/fedora/package-name@1.0-1.fc42?arch=x86_64",
      "externalReferences": [
        {
          "type": "cpe23Type",
          "url": "cpe:2.3:a:fedora:package-name:1.0:*:*:*:*:*:*:*:*"
        },
        {
          "type": "website",
          "url": "https://src.fedoraproject.org/rpms/package-name"
        },
        {
          "type": "distribution",
          "url": "package-name-1.0-1.fc42.src.rpm"
        }
      ],
      "licenses": [
        {
          "license": {
            "id": "MIT"
          }
        }
      ],
      "hashes": [
        {
          "alg": "SHA-256",
          "content": "..."
        }
      ],
      "properties": [
        {
          "name": "mock:rpm:vendor",
          "value": "Fedora Project"
        },
        {
          "name": "mock:rpm:buildhost",
          "value": "builder.fedora.example.org"
        },
        {
          "name": "mock:rpm:buildtime",
          "value": "2024-01-19T15:15:00+00:00"
        },
        {
          "name": "mock:rpm:sourcerpm",
          "value": "package-name-1.0-1.fc42.src.rpm"
        },
        {
          "name": "mock:signature:type",
          "value": "GPG"
        }
      ]
    }
  ],
  "dependencies": [
    {
      "ref": "pkg:rpm/fedora/package-name@1.0-1.fc42",
      "dependsOn": [
        "pkg:rpm/fedora/glibc@2.38-1.fc42"
      ]
    }
  ]
}
```

## Security Tool Compatibility

The generated CycloneDX SBOM is compatible with popular security scanners:

* **Grype**: `grype sbom:./sbom.cyclonedx.json`
* **Trivy**: `trivy sbom sbom.cyclonedx.json`
* **Snyk**: Supports CycloneDX format for vulnerability scanning

The SBOM includes PURL (Package URL) and CPE identifiers for accurate vulnerability matching.

## Requirements

* Python 3.x
* RPM tools for package metadata extraction
* Access to build environment for package information

## Notes

* The plugin runs in the `postbuild` hook, after the build completes
* SBOM generation is skipped if no RPM, source RPM, or spec file is found
* The plugin is designed to work with both source and binary RPM builds
* Build environment information is collected using `rpm -qa` command
* All build toolchain packages are captured, providing complete build provenance
* PURL format: `pkg:rpm/{distro}/{package}@{version}?arch={arch}`
* Mock-specific metadata is stored in component and metadata properties with `mock:` prefix

## Competitive Advantages

This SBOM generator leverages Mock's unique build environment visibility:

* **Complete Build Toolchain**: Captures every package installed in the build chroot, not just declared dependencies
* **Build-Time Provenance**: Records the exact build environment, including tool versions and signatures
* **RPM-Native Intelligence**: Deep integration with RPM metadata, spec files, and package signatures
* **Reproducible Build Context**: Complete build environment fingerprinting for reproducibility verification

Available since version 6.1. 