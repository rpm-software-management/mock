#!/usr/bin/python3 -tt
# -*- coding: utf-8 -*-
# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# SPDX-License-Identifier: GPL-2.0-or-later
# Written by Scott R. Shinn <scott@atomicorp.com>
# Copyright (C) 2026, Atomicorp, Inc.
# pylint: disable=invalid-name
"""
Generate a CycloneDX or SPDX SBOM from Mock build artifacts.

This tool is usable without running the full Mock toolchain.  Given a result
directory (and optionally a chroot root for toolchain/macro queries), it
produces the same SBOM artifacts as the sbom_generator plugin.
"""

import argparse
import json
import logging
import os
import subprocess
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("mock-sbom-generator")


class _SimpleLog:
    """Tiny logger duck-typed like buildroot.root_log."""

    def debug(self, msg, *args, **_kwargs):
        log.debug(msg, *args)

    def info(self, msg, *args, **_kwargs):
        log.info(msg, *args)

    def warning(self, msg, *args, **_kwargs):
        log.warning(msg, *args)

    def error(self, msg, *args, **_kwargs):
        log.error(msg, *args)


class StandaloneContext:
    """Minimal buildroot duck-type for standalone SBOM generation."""

    def __init__(self, rootdir, resultdir, mock_version=None, mock_config=None,
                 online=True, rpmbuild_networking=False, isolation=None,
                 use_nspawn=None, builddir=None):
        # None means "no chroot" — never treat the host "/" as the buildroot.
        self.rootdir = os.path.abspath(rootdir) if rootdir else None
        self.resultdir = os.path.abspath(resultdir)
        # Chroot-relative build dir, matching Buildroot.builddir semantics
        # (chroothome + "/build").
        if self.rootdir:
            self.builddir = builddir or "/builddir/build"
        else:
            self.builddir = None
        self.root_log = _SimpleLog()
        self.state = None
        self.config = {
            "version": mock_version or "unknown",
            "config_path": mock_config or "standalone",
            "online": online,
            "rpmbuild_networking": rpmbuild_networking,
        }
        if isolation is not None:
            self.config["isolation"] = isolation
        if use_nspawn is not None:
            self.config["use_nspawn"] = use_nspawn

    def make_chroot_path(self, *paths):
        """Join paths under rootdir; reject escapes via ``..`` or symlinks."""
        if not self.rootdir:
            return None
        root = os.path.realpath(self.rootdir)
        new_path = root
        for path in paths:
            relative = os.path.normpath(os.fspath(path).lstrip("/"))
            if relative in (".", ""):
                continue
            if relative == ".." or relative.startswith(".." + os.sep):
                raise ValueError(f"path escapes buildroot: {path!r}")
            new_path = os.path.realpath(os.path.join(new_path, relative))
            if os.path.commonpath((root, new_path)) != root:
                raise ValueError(f"path escapes buildroot: {path!r}")
        return new_path

    def from_chroot_path(self, host_path):
        from mockbuild.util import host_path_to_chroot_path
        return host_path_to_chroot_path(host_path, self.rootdir)

    def doOutChroot(self, command, *args, **kwargs):  # pylint: disable=invalid-name,unused-argument
        """Host-only stand-in for Mock's ``Buildroot.doOutChroot``.

        Execution model for SBOM generation:

        * **(a) Host** — used when bootstrap is disabled (Mock plugin runs the
          generator via ``util.do``) and always for this standalone CLI.
        * **(b) Bootstrap** — preferred Mock plugin path: stage the host-trusted
          tool into bootstrap and invoke it with real ``Buildroot.doOutChroot``
          (native bootstrap rpm against the target ``--root``).
        * **(c) Target chroot** — never used (supply-chain safety).

        This method is only the duck-type for standalone mode (no bootstrap).
        It runs ``command`` on the host (typically ``rpm --root <target>``),
        matching package_state. When Mock invokes the generator as a subprocess
        inside bootstrap, Mock's real ``doOutChroot`` is used instead — this
        method is not in that call path.
        """
        shell = kwargs.pop("shell", False)
        return_stderr = kwargs.pop("returnStderr", False)
        env = os.environ.copy()
        env["LC_ALL"] = "C"
        result = subprocess.run(
            command,
            shell=shell,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            text=True,
            env=env,
        )
        output = result.stdout or ""
        # rpm --checksig diagnostics (NOKEY, NOT OK) often land on stderr;
        # merge them like Buildroot.doOutChroot does with returnStderr=True.
        if return_stderr and result.stderr:
            output = (output + "\n" + result.stderr) if output else result.stderr
        return output, result.returncode


def _parse_bool(value):
    """Parse an explicit boolean CLI/config value.

    Raises:
        ValueError: If ``value`` is not a recognized true/false spelling.
    """
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in ("1", "true", "yes", "on"):
        return True
    if text in ("0", "false", "no", "off"):
        return False
    raise ValueError(
        f"invalid boolean value: {value!r} (expected true/false/yes/no/1/0)"
    )


def _argparser():
    parser = argparse.ArgumentParser(
        description="Generate CycloneDX/SPDX SBOM from RPM build artifacts.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--type",
        choices=("cyclonedx", "spdx"),
        default="cyclonedx",
        help="SBOM document format",
    )
    parser.add_argument(
        "--resultdir",
        required=True,
        help="Directory containing built RPMs/SRPMs (Mock result dir)",
    )
    parser.add_argument(
        "--root",
        default=None,
        help=(
            "Path to the Mock build chroot root (required for toolchain, "
            "distribution, and chroot RPM/macro queries). Omit to skip those "
            "collectors; never defaults to the host filesystem root."
        ),
    )
    parser.add_argument(
        "--builddir",
        default=None,
        help=(
            "Chroot-relative build directory (Buildroot.builddir / "
            "chroothome+/build). Default: /builddir/build"
        ),
    )
    parser.add_argument(
        "--prebuild-json",
        help="Optional JSON file with prebuild spec metadata and source files",
    )
    parser.add_argument("--mock-version", help="Mock version recorded in SBOM metadata")
    parser.add_argument("--mock-config", help="Mock config path recorded in SBOM metadata")
    parser.add_argument(
        "--online",
        default=None,
        help="Whether Mock had network access (config_opts['online'])",
    )
    parser.add_argument(
        "--rpmbuild-networking",
        default=None,
        help="Whether rpmbuild phases had network (config_opts['rpmbuild_networking'])",
    )
    parser.add_argument(
        "--isolation",
        default=None,
        help="Mock isolation mode (e.g. nspawn, simple, auto)",
    )
    parser.add_argument(
        "--use-nspawn",
        default=None,
        help="Whether systemd-nspawn was used for the build",
    )
    parser.add_argument("--include-file-components", default="true")
    parser.add_argument("--include-file-dependencies", default="false")
    parser.add_argument("--include-debug-files", default="false")
    parser.add_argument("--include-man-pages", default="true")
    parser.add_argument("--include-source-dependencies", default="true")
    parser.add_argument("--include-toolchain-dependencies", default="false")
    parser.add_argument(
        "--generate-cpe",
        default="false",
        help="Emit heuristic CPE identifiers (default: false; labeled confidence=heuristic)",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable debug logging"
    )
    return parser


def main(argv=None):
    parser = _argparser()
    args = parser.parse_args(argv)
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if not os.path.isdir(args.resultdir):
        log.error("Result directory does not exist: %s", args.resultdir)
        return 1

    rootdir = args.root
    if rootdir is not None:
        rootdir = os.path.abspath(rootdir)
        if not os.path.isdir(rootdir):
            log.error("Buildroot does not exist: %s", rootdir)
            return 1
        if os.path.realpath(rootdir) == "/":
            log.error(
                "--root must be a Mock build chroot, not the host filesystem root (/)"
            )
            return 1
    else:
        log.warning(
            "No --root given; skipping chroot toolchain/distribution collectors"
        )

    prebuild_source_files = []
    prebuild_spec_metadata = {}
    prebuild_capture_errors = []
    prebuild_input_srpm = None
    injected_host_properties = []
    injected_hardening_properties = []
    build_env = {}
    if args.prebuild_json:
        try:
            with open(args.prebuild_json, "r", encoding="utf-8") as handle:
                state = json.load(handle)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            log.error("Cannot load prebuild JSON %s: %s", args.prebuild_json, exc)
            return 1
        if not isinstance(state, dict):
            log.error(
                "Prebuild JSON must contain an object: %s", args.prebuild_json
            )
            return 1
        for key, expect_type, label in (
            ("source_files", list, "list"),
            ("spec_metadata", dict, "object"),
            ("capture_errors", list, "list"),
            ("build_env", dict, "object"),
            ("host_metadata_properties", list, "list"),
            ("hardening_properties", list, "list"),
        ):
            if key not in state or state.get(key) is None:
                continue
            if not isinstance(state.get(key), expect_type):
                log.error(
                    "Prebuild JSON field %r must be a %s: %s",
                    key, label, args.prebuild_json,
                )
                return 1
        prebuild_source_files = state.get("source_files") or []
        prebuild_spec_metadata = state.get("spec_metadata") or {}
        prebuild_capture_errors = state.get("capture_errors") or []
        prebuild_input_srpm = state.get("input_srpm")
        injected_host_properties = state.get("host_metadata_properties") or []
        injected_hardening_properties = state.get("hardening_properties") or []
        build_env = state.get("build_env") or {}

        for label, props in (
            ("host_metadata_properties", injected_host_properties),
            ("hardening_properties", injected_hardening_properties),
        ):
            for idx, entry in enumerate(props):
                if not isinstance(entry, dict) or "name" not in entry or "value" not in entry:
                    log.error(
                        "Prebuild JSON %s[%d] must be "
                        "{\"name\": ..., \"value\": ...}: %s",
                        label, idx, args.prebuild_json,
                    )
                    return 1

    def _cli_bool(raw, flag_name):
        try:
            return _parse_bool(raw)
        except ValueError as exc:
            log.error("%s: %s", flag_name, exc)
            raise SystemExit(1) from exc

    # CLI flags override values captured in prebuild JSON when provided.
    online = (
        _cli_bool(args.online, "--online") if args.online is not None
        else build_env.get("online", True)
    )
    rpmbuild_networking = (
        _cli_bool(args.rpmbuild_networking, "--rpmbuild-networking")
        if args.rpmbuild_networking is not None
        else build_env.get("rpmbuild_networking", False)
    )
    isolation = args.isolation if args.isolation is not None else build_env.get("isolation")
    if args.use_nspawn is not None:
        use_nspawn = _cli_bool(args.use_nspawn, "--use-nspawn")
    elif "use_nspawn" in build_env:
        use_nspawn = build_env.get("use_nspawn")
    else:
        use_nspawn = None

    try:
        conf = {
            "generate_sbom": True,
            "type": args.type,
            "include_file_components": _parse_bool(args.include_file_components),
            "include_file_dependencies": _parse_bool(args.include_file_dependencies),
            "include_debug_files": _parse_bool(args.include_debug_files),
            "include_man_pages": _parse_bool(args.include_man_pages),
            "include_source_dependencies": _parse_bool(args.include_source_dependencies),
            "include_toolchain_dependencies": _parse_bool(
                args.include_toolchain_dependencies
            ),
            "generate_cpe": _parse_bool(args.generate_cpe),
        }
    except ValueError as exc:
        log.error("%s", exc)
        return 1

    context = StandaloneContext(
        rootdir=rootdir,
        resultdir=args.resultdir,
        mock_version=args.mock_version,
        mock_config=args.mock_config,
        online=online,
        rpmbuild_networking=rpmbuild_networking,
        isolation=isolation,
        use_nspawn=use_nspawn,
        builddir=args.builddir,
    )
    # Late import so argparse-manpage can load this module without rpm bindings.
    from mockbuild.sbom_generate import SBOMGenerator

    generator = SBOMGenerator(
        conf,
        context,
        prebuild_source_files=prebuild_source_files,
        prebuild_spec_metadata=prebuild_spec_metadata,
        prebuild_capture_errors=prebuild_capture_errors,
        prebuild_input_srpm=prebuild_input_srpm,
        injected_host_properties=injected_host_properties,
        injected_hardening_properties=injected_hardening_properties,
    )
    if not generator.generate():
        log.error("SBOM generation failed; no SBOM artifact was written")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
