---
layout: default
title: Plugin SBOM Generator
---

This plugin generates a Software Bill of Materials (SBOM) in CycloneDX and SPDX formats for packages built with Mock. The SBOM provides detailed information about the build environment, source files, and resulting packages, optimized for security use cases.

## Features

* Generates SBOM in CycloneDX 1.6 format (JSON) and SPDX 2.3 format
* Deep Chroot Integration:
  * With bootstrap enabled, postbuild runs the host-trusted generator **inside
    bootstrap** via `doOutChroot` (bootstrap-native `rpm` / `python3-rpm`), with
    the target root queried via `--root` — never executed in the target buildroot.
  * With `use_bootstrap=False`, the generator runs on the host (same CLI).
  * Correctly handles path mapping between chroot and host environments.
* Captures detailed information about:
  * Source files and patches from spec files with a resilient regex-based fallback for legacy/strict syntax errors.
  * Binary RPM metadata with standard PURL identifiers, and CPE identifiers
    when ``--generate-cpe`` is enabled in the generator command.
  * Build toolchain packages with per-package GPG signature metadata when
    available (best-effort; see ``sbom:completeness`` and collection errors).
  * Runtime dependencies.
  * File hashes (SHA-256).
* Optimized Performance: Consolidated file listing and metadata extraction into a single pass.
* Outputs SBOM in the build results directory.
* Compatible with security scanners (Grype, Trivy, Snyk).
* Standalone CLI: `mock-sbom-generator` can generate an SBOM from a result directory
  without running a full Mock build. The plugin invokes this tool after the build.
* Retains `sbom-prebuild.json` in the result directory as a forensic snapshot of
  pre-build sources/spec metadata.

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

After the build completes, the SBOM is written to the results directory as
`<name>-<version>-<release>.sbom` (CycloneDX) or
`<name>-<version>-<release>.spdx.json` (SPDX). Examples below use
`package-1.0-1.fc42.sbom` to match the sample rebuild above.

### Viewing and Analyzing the SBOM

The generated SBOM can be analyzed using various tools:

```bash
# View basic SBOM information
jq '.metadata.component' package-1.0-1.fc42.sbom
jq '.components | length' package-1.0-1.fc42.sbom
jq '.dependencies | length' package-1.0-1.fc42.sbom

# List all built packages (exclude build-toolchain role)
jq '.components[]
  | select(.type == "library" or .type == "application")
  | select(any(.properties[]?; .name == "mock:role" and .value == "build-toolchain") | not)
  | {name, version, purl}' package-1.0-1.fc42.sbom

# List source files used in the build
jq '.components[] | select(.properties[]?.name == "mock:source:type") | {name, hashes}' package-1.0-1.fc42.sbom

# View runtime dependencies for a specific package
jq '.dependencies[] | select(.ref | contains("httpd"))' package-1.0-1.fc42.sbom
```

### Using with Security Scanners

The SBOM can be directly used with security vulnerability scanners:

```bash
# Scan with SBOM Auditor
sbom-auditor package-1.0-1.fc42.sbom

# Scan with Grype
grype sbom:./package-1.0-1.fc42.sbom

# Scan with Trivy
trivy sbom package-1.0-1.fc42.sbom

# Native SPDX via mock-sbom-generator (writes <n>-<v>-<r>.spdx.json in resultdir)
mock-sbom-generator --type spdx --resultdir . --root /var/lib/mock/ROOT/root
# Or generate SPDX JSON from the built package with Syft:
syft package-1.0-1.fc42.x86_64.rpm -o spdx-json > package-1.0-1.fc42.spdx.json
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

The plugin has two options. Generator behavior (format, includes, CPE, …) is
controlled by editing the ``command`` string — so a different host SBOM tool can
be plugged in without new Mock config keys.

```python
config_opts['plugin_conf']['sbom_generator_opts'] = {
    'generate_sbom': True,              # Enable SBOM generation (default: True)
    # Full argv template. Generator flags are literal defaults; override this
    # string to change format/includes or to point at an external generator.
    # Mock fills only path/runtime placeholders at postbuild.
    'command': (
        '/usr/bin/mock-sbom-generator'
        ' --type cyclonedx'
        ' --resultdir %(resultdir)s'
        ' --root %(root)s'
        ' --builddir %(builddir)s'
        ' --include-file-components true'
        ' --include-file-dependencies false'
        ' --include-debug-files false'
        ' --include-man-pages true'
        ' --include-source-dependencies true'
        ' --include-toolchain-dependencies false'
        ' --generate-cpe false'
        ' --online %(online)s'
        ' --rpmbuild-networking %(rpmbuild_networking)s'
        ' --isolation %(isolation)s'
        ' --use-nspawn %(use_nspawn)s'
    ),
}
```

**Examples — customize via ``command``:**

```python
# SPDX instead of CycloneDX
config_opts['plugin_conf']['sbom_generator_opts']['command'] = (
    '/usr/bin/mock-sbom-generator'
    ' --type spdx'
    ' --resultdir %(resultdir)s'
    ' --root %(root)s'
    ' --builddir %(builddir)s'
    ' --online %(online)s'
    ' --rpmbuild-networking %(rpmbuild_networking)s'
    ' --isolation %(isolation)s'
    ' --use-nspawn %(use_nspawn)s'
)

# External generator (Mock still injects paths)
config_opts['plugin_conf']['sbom_generator_opts']['command'] = (
    '/usr/bin/my-sbom-tool --out %(resultdir)s --chroot %(root)s'
)
```

**Standalone usage (no Mock build required):**

```bash
mock-sbom-generator --type cyclonedx \
    --resultdir /var/lib/mock/fedora-rawhide-x86_64/result \
    --root /var/lib/mock/fedora-rawhide-x86_64/root
```

Pass `--root` for toolchain/distribution collectors. Omitting it skips those
collectors; `--root /` is rejected so host RPMs are never recorded as the
toolchain.

**Configuration Options Explained:**

- `generate_sbom`: Enable or disable generation when the plugin is loaded
  (default: `True`).
- `command`: Full argv **template** for the generator (default embeds
  `mock-sbom-generator` with sensible literal flags). Use Python `%(name)s`
  placeholders for values Mock fills at postbuild: `resultdir`, `root`,
  `builddir`, and live network/isolation settings (`online`,
  `rpmbuild_networking`, `isolation`, `use_nspawn`). Put generator-specific
  flags (`--type`, `--include-*`, `--generate-cpe`, …) literally in the string
  (or rely on CLI defaults). Replace the template to run an external tool while
  keeping path injection. Optional provenance flags (`--prebuild-json`,
  `--mock-version`, `--mock-config`) are appended by the plugin when available;
  `--mock-config` is a config **file** path label for provenance, not an
  expanded config dump.
  With bootstrap enabled, a host absolute `argv[0]` is bind-mounted into
  bootstrap for the run (or the default generator is copied under
  `/usr/libexec/mock-sbom/`). Paths inside the **target** buildroot are refused.

**CLI flags on ``mock-sbom-generator``** (embed in ``command`` as needed):

- `--type`: `cyclonedx` (default) or `spdx`.
- `--generate-cpe`: Heuristic CPE identifiers labeled
  `mock:cpe:confidence=heuristic` (default: off, to avoid false vulnerability
  matches from fabricated CPEs).
- `--include-file-components`: Individual file components with hashes,
  permissions, and ownership (default: on).
- `--include-file-dependencies`: File-to-package dependency relationships
  (default: off).
- `--include-debug-files`: Include `.debug` / `/usr/lib/debug` paths in file
  components (default: off).
- `--include-man-pages`: Include man/info pages in file components
  (default: on).
- `--include-source-dependencies`: Primary component `dependsOn` includes
  build-input source/patch bom-refs (default: on).
- `--include-toolchain-dependencies`: Add toolchain bom-refs to package
  dependency graphs (default: off; can make graphs very large).

## Output

The plugin generates a file named `<name>-<version>-<release>.sbom` (for CycloneDX) or `<name>-<version>-<release>.spdx.json` (for SPDX) in the build results directory (never a generic name like `plugin.sbom`). The SBOM includes:

* CycloneDX/SPDX document metadata
  * Build timestamp
  * Tool information (Mock SBOM Generator)
  * Mock-specific build properties (host, distribution, chroot, config)
  * Network / isolation status from the live Mock build:
    * `mock:build:network:online` (`config_opts['online']`)
    * `mock:build:network:rpmbuild` (`config_opts['rpmbuild_networking']`)
    * `mock:build:isolation` / `mock:build:nspawn` when set
  * Evidence-backed completeness: `sbom:completeness` is computed from collector
    success (`complete` / `partial` / `minimal`); failures are listed in
    `mock:sbom:collection_errors`
  * Signature status tri-state: `verified` / `present-unverified` / `unsigned`
    (never claims valid without cryptographic check)
  * Host forensics: kernel, SELinux mode, host distribution
  * Sidecar digest: `<sbom>.sha256`
  * RPM header metadata surfaced at the document level (buildhost, buildtime, group, epoch, distribution)
  * Component manufacturer from RPM Vendor (not BOM author); packager as supplier when present
* Components array containing:
  * Built packages (type: "library" or "application")
    * Package name, version, and PURL
    * CPE identifiers for vulnerability matching (only when `--generate-cpe` is enabled)
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
  * With default `include_source_dependencies=True`, the primary component also
    `dependsOn` build-input source/patch bom-refs. Set that option `False` to
    keep sources only in `components[]` / formulation.
  * Toolchain bom-refs are added to `dependsOn` only when
    `include_toolchain_dependencies=True` (default `False`)

### Interpreting auditor WARN findings

When auditing with `sbom-auditor`, some WARN results are expected depending on build policy:

* **Hermetic Build** — PASS only when both `config_opts['online'] = False` and
  `config_opts['rpmbuild_networking'] = False`. Default Mock configs that enable
  network for dependency download correctly score WARN (`online=true`).
* **Build-output signatures** — Freshly built binary RPMs and the *rebuilt*
  result-dir ``*.src.rpm`` correctly report `mock:signature:status=unsigned`.
  Chain-of-custody checks the *input* SRPM from Mock's
  ``builddir/build/originals/`` (captured at prebuild). A signed vendor SRPM
  should appear as a build-input with `mock:source:type=source_rpm`. Toolchain
  packages from the chroot must report `verified` (or `present-unverified` if
  the keyring cannot confirm the key). An all-unsigned toolchain is a generator
  failure.
* **Hardening `pie_enabled` / `fips_enabled`** — Emitted as `true`/`false` only
  when macros or the FIPS sysctl were successfully read. Missing evidence is
  omitted (unknown), not reported as `false`.

## Example SBOM Structure

Abbreviated CycloneDX example (runtime edges only). With the default
``include_source_dependencies=True``, the primary component's ``dependsOn``
also includes source/patch bom-refs omitted here for brevity.

```json
{
  "bomFormat": "CycloneDX",
  "specVersion": "1.6",
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
      { "name": "mock:rpm:group", "value": "System Environment/Libraries" },
      { "name": "mock:rpm:epoch", "value": "1" }
    ],
    "component": {
      "type": "application",
      "name": "package-name",
      "version": "1.0-1.fc42",
      "bom-ref": "build-output:package-name",
      "description": "Package summary (build output containing 3 package(s))",
      "manufacturer": {
        "name": "Fedora Project"
      },
      "licenses": [
        {
          "expression": "MIT"
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
          "type": "other",
          "comment": "CPE 2.3 (heuristic)",
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
          "expression": "MIT"
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
          "name": "mock:signature:type",
          "value": "GPG"
        },
        {
          "name": "mock:signature:status",
          "value": "verified"
        }
      ]
    }
  ],
  "dependencies": [
    {
      "ref": "pkg:rpm/fedora/package-name@1.0-1.fc42?arch=x86_64",
      "dependsOn": [
        "pkg:rpm/fedora/glibc@2.38-1.fc42"
      ]
    }
  ]
}
```

## Security Tool Compatibility

The generated CycloneDX SBOM is compatible with popular security scanners:

* **Grype**: `grype sbom:./package-1.0-1.fc42.sbom`
* **Trivy**: `trivy sbom package-1.0-1.fc42.sbom`
* **Snyk**: Supports CycloneDX format for vulnerability scanning

The SBOM includes PURL (Package URL) identifiers for accurate package identity.
CPE identifiers are included only when `--generate-cpe` is enabled in the generator command.

## Requirements

* Python 3.x
* Access to build environment for package information
* Native `rpm` and `specfile` libraries (recommended)

## Notes

* The plugin captures ``sbom-prebuild.json`` in a prebuild hook (sources/spec
  snapshot), then generates the SBOM in the ``postbuild`` hook after the build
  completes. At postbuild the plugin also injects host forensics
  (``host_metadata_properties``: hostname, SELinux, host distro/kernel) and
  hardening macro properties (``hardening_properties``, via host
  ``rpm --root``) into that JSON so bootstrap execution does not under-report
  them.
* SBOM generation is skipped if no RPM, source RPM, or spec file is found.
* **Best-effort postbuild**: if SBOM generation fails, Mock logs a warning and
  the package build still succeeds. The standalone `mock-sbom-generator` CLI
  exits non-zero on failure.
* **Trust boundary**: Host supplies the generator binary/modules; bootstrap
  (or host if bootstrap is off) executes them with native `rpm`; the target
  buildroot is queried only via `--root` and never runs the generator.
  Host policy/hardening attestation is captured on the Mock host and passed
  into the generator; RPM inventory and signature checks still use bootstrap
  (or host) native `rpm`.
* **Bootstrap execution**: Postbuild copies the host-trusted tool into
  `/usr/libexec/mock-sbom/` inside bootstrap, bind-mounts `resultdir`, and runs
  via `doOutChroot`. Bootstrap may install `python3` / `python3-rpm` for that
  purpose.
* **Resilient Parsing**: Includes a regex-based fallback for spec files that fail strict parsing by the `specfile` library (e.g., legacy `%patchN` syntax).
* **PURL format**: `pkg:rpm/{distro}/{package}@{version}?arch={arch}`. Architecture is always separated into a qualifier, never baked into the version string.
* Mock-specific metadata is stored in properties with the `mock:` prefix.

## Competitive Advantages

This SBOM generator leverages Mock's unique build environment visibility:

* **Build Toolchain Visibility**: Captures installed chroot packages when
  collectors succeed (not only declared BuildRequires); coverage is reported via
  ``sbom:completeness``
* **Build-Time Provenance**: Records build-environment metadata, including tool
  versions and signature status when available
* **RPM-Native Intelligence**: Deep integration with RPM metadata, spec files, and package signatures
* **Reproducible Build Context**: Build-environment fingerprinting to support
  reproducibility verification

Available since version 6.7. 