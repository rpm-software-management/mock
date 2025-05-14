import os
import json
import subprocess
from mockbuild.trace_decorator import traceLog
import hashlib
import re

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
        plugins.add_hook("prebuild", self._listSPECSDirectory)
        plugins.add_hook("postbuild", self._generateSBOMPostBuildHook)

    @traceLog()
    def _listSPECSDirectory(self):
        """Lists the contents of the SPECS directory before building."""

        print("DEBUG: Listing contents of SPECS directory before building:")
#        print(f"Buildroot values:") 
#        for key, value in vars(self.buildroot).items():
#            print(f"   {key}: {value}")
        print(f"DEBUG: builddir is {self.buildroot.builddir}")
        print(f"DEBUG: rootdir is {self.rootdir}")
        print(f"DEBUG: resultsdir is {self.buildroot.resultdir}")

        # specs_dir is rootdir + builddir + SPECS
        #specs_dir = os.path.join(self.buildroot.rootdir, self.buildroot.builddir, "rpmbuild/SPECS")
        specs_dir = os.path.join(self.rootdir, "/foo/", "/bar/")
        print(f"DEBUG: spec dir is {specs_dir}")

        try:
            if os.path.exists(specs_dir):
                specs_files = os.listdir(specs_dir)
                print(f"Contents of SPECS directory: {specs_files}")
            else:
                print("SPECS directory does not exist.")
        except Exception as e:
            print(f"Failed to list contents of SPECS directory: {e}")

    @traceLog()
    def _generateSBOMPostBuildHook(self):
        if self.sbom_done or not self.sbom_enabled:
            return

        out_file = os.path.join(self.buildroot.resultdir, 'sbom.spdx.json')
        state_text = "Generating SBOM for built packages v0.8"
        self.state.start(state_text)

        try:
            build_dir = self.buildroot.resultdir
            rpm_files = [f for f in os.listdir(build_dir) if f.endswith('.rpm')]
            src_rpm_files = [f for f in os.listdir(build_dir) if f.endswith('.src.rpm')]
            spec_file = next((f for f in os.listdir(build_dir) if f.endswith('.spec')), None)

            if not rpm_files and not src_rpm_files and not spec_file:
                print("No RPM, source RPM, or spec file found for SBOM generation.")
                return

            sbom = {
                "SPDXVersion": "SPDX-2.3",
                "DataLicense": "CC0-1.0",
                "SPDXID": "SPDXRef-DOCUMENT",
                "name": "mock-build",
                "creator": "Mock-SBOM-Plugin",
                "created": self.get_iso_timestamp(),
                "packages": [],
                "source_package": {}
            }

            # Process spec file for sources and patches
            if spec_file:
                spec_path = os.path.join(build_dir, spec_file)
                source_files = self.parse_spec_file(spec_path)
                sbom["source_package"]["source_files"] = source_files

            build_environment = self.get_build_environment_packages()

            # Process binary RPMs
            for rpm_file in rpm_files:
                rpm_path = os.path.join(build_dir, rpm_file)
                package_data = self.get_rpm_metadata(rpm_path)
                if package_data:
                    sbom_package = {
                        "name": package_data.get("name"),
                        "version": package_data.get("version"),
                        "release": package_data.get("release"),
                        "license": package_data.get("license"),
                        "vendor": package_data.get("vendor"),
                        "url": package_data.get("url"),
                        "packager": package_data.get("packager"),
                        "files": [],
                        "dependencies": [],
                        "gpg_signature": None,
                    }
                    sbom["packages"].append(sbom_package)

            sbom["build_environment"] = build_environment

            with open(out_file, "w") as f:
                json.dump(sbom, f, indent=4)

            print(f"SBOM successfully written to: {out_file}")
        except Exception as e:
            print(f"An error occurred during SBOM generation: {e}")
        finally:
            self.sbom_done = True
            self.state.finish(state_text)

    def parse_spec_file(self, spec_path):
        """Parses a spec file to extract source and patch files."""

        # print that we're in this function
        print("Parsing spec file")
        # does spec file exist? if not print what it was looking for
        if not os.path.isfile(spec_path):
            print(f"Spec file not found: {spec_path}")
            return []
        sources = []
        try:
            with open(spec_path, 'r') as spec:
                for line in spec:
                    line = line.strip()
                    # Match lines like Source0: or Patch1:
                    match = re.match(r'^(Source|Patch)[0-9]*:\s*(.+)$', line)
                    if match:
                        sources.append(match.group(2))
            print(f"Extracted source and patch files from spec: {sources}")
        except Exception as e:
            print(f"Failed to parse spec file {spec_path}: {e}")
        return sources

    def get_iso_timestamp(self):
        """Returns the current time in ISO 8601 format."""
        from datetime import datetime
        return datetime.utcnow().isoformat() + "Z"

    def get_build_environment_packages(self):
        """Returns the list of packages installed in the build environment."""
        try:
            cmd = "rpm -qa --qf '%{NAME} %{VERSION}-%{RELEASE}.%{ARCH} %{SIGPGP}\n'"
            output, _ = self.buildroot.doOutChroot(cmd, returnOutput=True, shell=True)
            packages = []
            for line in output.splitlines():
                parts = line.split()
                if len(parts) >= 3:
                    packages.append({
                        "name": parts[0],
                        "version": parts[1],
                        "digital_signature": parts[2] if len(parts) > 2 else None
                    })
            #print(f"Build environment packages: {packages}")
            return packages
        except Exception as e:
            print(f"Failed to retrieve build environment packages: {e}")
            return []

    def get_rpm_metadata(self, rpm_path):
        """Extracts metadata from an RPM file."""
        if not os.path.isfile(rpm_path):
            print(f"RPM file not found: {rpm_path}")
            return {}

        cmd = ["rpm", "-qp", rpm_path, "--queryformat",
               "\{\"name\": \"%{NAME}\", \"version\": \"%{VERSION}\", \"release\": \"%{RELEASE}\", \"arch\": \"%{ARCH}\", \"summary\": \"%{SUMMARY}\", \"license\": \"%{LICENSE}\", \"vendor\": \"%{VENDOR}\", \"url\": \"%{URL}\", \"packager\": \"%{PACKAGER}\"\}"]
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True)
            if not result.stdout.strip():
                print(f"No output from RPM command for {rpm_path}")
                print(f"Command run: {cmd}")
                return {}

            print(f"RPM command output: {result.stdout}")
            return json.loads(result.stdout)
        except subprocess.CalledProcessError as e:
            print(f"RPM command failed for {rpm_path}: {e.stderr}")
            return {}
        except json.JSONDecodeError as e:
            print(f"Failed to parse RPM metadata output: {result.stdout}")
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
                    print(f"GPG Signature for {rpm_path}: {line}")
                    return line
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
