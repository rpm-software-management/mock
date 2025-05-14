---
layout: default
title: Plugin SBOM Generator
---

This plugin generates a Software Bill of Materials (SBOM) in SPDX format for packages built with Mock. The SBOM provides detailed information about the build environment, source files, and resulting packages.

## Features

* Generates SBOM in SPDX 2.3 format
* Captures information about:
  * Source files and patches from spec files
  * Binary RPM metadata
  * Build environment packages
  * Dependencies
  * File lists
  * GPG signatures
* Outputs SBOM as JSON file in the build results directory

## Configuration

The plugin is disabled by default. To enable it, add this to your configuration:

```python
config_opts['plugin_conf']['sbom_generator_enable'] = True
config_opts['plugin_conf']['sbom_generator_opts'] = {
    'generate_sbom': True
}
```

You can also enable it for a single build using the command line:

    mock --enable-plugin=sbom_generator --rebuild package.src.rpm

## Output

The plugin generates a file named `sbom.spdx.json` in the build results directory (typically `/var/lib/mock/fedora-42-x86_64/result/`). The SBOM includes:

* SPDX version and metadata
* Source package information
  * Source files
  * Patch files
* Binary package information
  * Package name, version, and release
  * License information
  * Vendor and URL
  * Packager information
  * File lists
  * Dependencies
  * GPG signatures
* Build environment information
  * List of installed packages
  * Package versions
  * Digital signatures

## Example SBOM Structure

```json
{
    "SPDXVersion": "SPDX-2.3",
    "DataLicense": "CC0-1.0",
    "SPDXID": "SPDXRef-DOCUMENT",
    "name": "mock-build",
    "creator": "Mock-SBOM-Plugin",
    "created": "2024-01-19T15:20:00Z",
    "packages": [
        {
            "name": "package-name",
            "version": "1.0",
            "release": "1.fc42",
            "license": "MIT",
            "vendor": "Fedora Project",
            "url": "https://example.com",
            "packager": "Fedora Project",
            "files": [],
            "dependencies": [],
            "gpg_signature": null
        }
    ],
    "source_package": {
        "source_files": [
            "source0.tar.gz",
            "patch1.patch"
        ]
    },
    "build_environment": [
        {
            "name": "package-name",
            "version": "1.0-1.fc42",
            "digital_signature": "RSA/SHA256, ..."
        }
    ]
}
```

## Requirements

* Python 3.x
* RPM tools for package metadata extraction
* Access to build environment for package information

## Notes

* The plugin runs in the `postbuild` hook, after the build completes
* SBOM generation is skipped if no RPM, source RPM, or spec file is found
* The plugin is designed to work with both source and binary RPM builds
* Build environment information is collected using `rpm -qa` command

Available since version 6.1. 