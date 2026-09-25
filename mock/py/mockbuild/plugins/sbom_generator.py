# -*- coding: utf-8 -*-
# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# SPDX-License-Identifier: GPL-2.0-or-later
# Written by Scott R. Shinn <scott@atomicorp.com>
# Copyright (C) 2026, Atomicorp, Inc.
"""Mock plugin that invokes mock-sbom-generator after a successful build."""

import glob
import json
import os
import shlex
import shutil
import sys
from contextlib import ExitStack, contextmanager

from mockbuild.mounts import BindMountPoint
from mockbuild.sbom_utils import RpmQueryHelper
import mockbuild.file_util
import mockbuild.util

# pylint: disable=invalid-name
requires_api_version = "1.1"
# pylint: enable=invalid-name

# Host path for the packaged generator (also the default command argv[0]).
DEFAULT_GENERATOR_PATH = "/usr/bin/mock-sbom-generator"

# Full argv template (rpkg_preprocessor-style). Generator-specific flags are
# literal defaults here; override the whole ``command`` string to change
# format/includes or to point at an external tool. Mock only substitutes
# path/runtime placeholders at postbuild: resultdir, root, builddir, online,
# rpmbuild_networking, isolation, use_nspawn.
DEFAULT_COMMAND = (
    f"{DEFAULT_GENERATOR_PATH}"
    " --type cyclonedx"
    " --resultdir %(resultdir)s"
    " --root %(root)s"
    " --builddir %(builddir)s"
    " --include-file-components true"
    " --include-file-dependencies false"
    " --include-debug-files false"
    " --include-man-pages true"
    " --include-source-dependencies true"
    " --include-toolchain-dependencies false"
    " --generate-cpe false"
    " --online %(online)s"
    " --rpmbuild-networking %(rpmbuild_networking)s"
    " --isolation %(isolation)s"
    " --use-nspawn %(use_nspawn)s"
)

# Staged location inside the bootstrap chroot (host-trusted copy, never target).
BOOTSTRAP_SBOM_LIBEXEC = "/usr/libexec/mock-sbom"
BOOTSTRAP_SBOM_SCRIPT = f"{BOOTSTRAP_SBOM_LIBEXEC}/mock-sbom-generator"

# Host-side modules copied into bootstrap under BOOTSTRAP_SBOM_LIBEXEC/mockbuild/.
_BOOTSTRAP_MODULE_FILES = (
    "__init__.py",
    "exception.py",
    "installed_packages.py",
    "sbom_cyclonedx.py",
    "sbom_generate.py",
    "sbom_spdx.py",
    "sbom_utils.py",
)

# Visible forensic artifact retained in the result directory
PREBUILD_STATE_FILENAME = "sbom-prebuild.json"
# Legacy hidden name from earlier builds (still accepted if present)
LEGACY_PREBUILD_STATE_FILENAME = ".sbom-prebuild.json"


def init(plugins, conf, buildroot):
    """Initializes the SBOM generator plugin."""
    SBOMGeneratorPlugin(plugins, conf, buildroot)


class SBOMGeneratorPlugin:
    """Thin plugin wrapper that captures prebuild state and calls the CLI tool."""

    # pylint: disable=too-few-public-methods
    def __init__(self, plugins, conf, buildroot):
        self.buildroot = buildroot
        self.conf = conf
        self.rpm_helper = RpmQueryHelper(self.buildroot)
        self.state = buildroot.state
        self.sbom_enabled = self.conf.get("generate_sbom", True)
        self.command = self.conf.get("command", DEFAULT_COMMAND)
        self.sbom_done = False
        self.prebuild_state_path = os.path.join(
            self.buildroot.resultdir, PREBUILD_STATE_FILENAME
        )

        if self.sbom_enabled:
            plugins.add_hook("prebuild", self._capture_prebuild_state)
            plugins.add_hook("postbuild", self._run_sbom_generator)

    def _capture_input_srpm(self):
        """Record the original (signed) input SRPM from Mock's originals/ tree.

        The result-dir ``*.src.rpm`` is a rebuilt, typically unsigned artifact.
        Chain-of-custody checks must use the pristine input under
        ``<builddir>/originals/`` (honoring ``config_opts['chroothome']``).
        """
        originals_dir = self.buildroot.make_chroot_path(
            self.buildroot.builddir, "originals"
        )
        try:
            return self.rpm_helper.capture_originals_input_srpm(originals_dir)
        except OSError as exc:
            self.buildroot.root_log.warning(
                "[SBOM] Failed scanning originals for input SRPM: %s", exc
            )
        return None

    def _capture_prebuild_state(self):
        """Captures pristine source artifacts before the build begins.

        Runs under ``uid_manager`` (mockbuild) and refuses to follow symlinks
        that escape the chroot when hashing SPECS/SOURCES/originals.
        """
        self.buildroot.root_log.debug("Capturing pre-build state from SPECS and SOURCES")
        specs_dir = self.buildroot.make_chroot_path(self.buildroot.builddir, "SPECS")
        state = {
            "spec_metadata": {},
            "source_files": [],
            "input_srpm": None,
            "build_env": self._build_env_snapshot(),
            "capture_errors": [],
        }
        try:
            with self.buildroot.uid_manager:
                specs_safe = (
                    bool(specs_dir)
                    and os.path.exists(specs_dir)
                    and self.rpm_helper.path_stays_in_chroot(specs_dir)
                )
                if specs_dir and os.path.exists(specs_dir) and not specs_safe:
                    msg = "SPECS directory resolves outside the build chroot"
                    state["capture_errors"].append(msg)
                    self.buildroot.root_log.warning("[SBOM] %s", msg)
                elif specs_safe:
                    try:
                        with os.scandir(specs_dir) as entries:
                            for entry in entries:
                                if entry.is_symlink():
                                    self.buildroot.root_log.warning(
                                        "[SBOM] Skipping symlink in SPECS: %s",
                                        entry.path,
                                    )
                                    continue
                                if entry.name.endswith(".spec") and entry.is_file(
                                    follow_symlinks=False
                                ):
                                    self.buildroot.root_log.debug(
                                        "Parsing spec file for pre-build state: %s",
                                        entry.path,
                                    )
                                    try:
                                        metadata, sources = (
                                            self.rpm_helper.parse_spec_file(
                                                entry.path
                                            )
                                        )
                                        state["spec_metadata"] = metadata
                                        state["source_files"] = sources
                                        if not (metadata or {}).get("name"):
                                            msg = (
                                                "spec parse produced empty name "
                                                f"for {entry.path}"
                                            )
                                            state["capture_errors"].append(msg)
                                            self.buildroot.root_log.warning(
                                                "[SBOM] %s", msg
                                            )
                                    except Exception as exc:  # pylint: disable=broad-exception-caught
                                        msg = (
                                            f"Failed parsing spec {entry.path}: {exc}"
                                        )
                                        state["capture_errors"].append(msg)
                                        self.buildroot.root_log.warning(
                                            "[SBOM] %s", msg
                                        )
                                    break
                    except OSError as exc:
                        msg = f"Failed scanning SPECS directory: {exc}"
                        state["capture_errors"].append(msg)
                        self.buildroot.root_log.warning("[SBOM] %s", msg)
                else:
                    msg = "SPECS directory does not exist for pre-build capture"
                    state["capture_errors"].append(msg)
                    self.buildroot.root_log.warning("[SBOM] %s", msg)

                # Always attempt input-SRPM capture even if spec parsing failed.
                input_srpm = self._capture_input_srpm()
                if input_srpm:
                    state["input_srpm"] = input_srpm
                    sources = list(state.get("source_files") or [])
                    if not any(
                        e.get("source_type") == "source_rpm"
                        or (
                            e.get("role") == "input"
                            and (e.get("filename") or "").endswith(".src.rpm")
                        )
                        for e in sources
                    ):
                        sources.insert(0, input_srpm)
                        state["source_files"] = sources
                    self.buildroot.root_log.debug(
                        "[SBOM] Captured input SRPM %s (%s)",
                        input_srpm.get("filename"),
                        (input_srpm.get("digital_signature") or {}).get(
                            "signature_status", "unknown"
                        ),
                    )
                else:
                    # Spec-file builds often have no originals/ SRPM; only treat
                    # that as a capture gap when we also lack usable spec metadata.
                    if not (state.get("spec_metadata") or {}).get("name"):
                        msg = (
                            "No input SRPM found under the chroot originals/ directory"
                        )
                        state["capture_errors"].append(msg)
                        self.buildroot.root_log.warning("[SBOM] %s", msg)
                    else:
                        self.buildroot.root_log.debug(
                            "[SBOM] No input SRPM under originals/ "
                            "(spec-based build; skipping capture error)"
                        )

                os.makedirs(self.buildroot.resultdir, exist_ok=True)
                with open(self.prebuild_state_path, "w", encoding="utf-8") as handle:
                    json.dump(state, handle, indent=2)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self.buildroot.root_log.warning(
                "Failed to capture pre-build state: %s", exc
            )
            # Still write a stub so postbuild can record the failure
            try:
                state["capture_errors"].append(str(exc))
                os.makedirs(self.buildroot.resultdir, exist_ok=True)
                with open(self.prebuild_state_path, "w", encoding="utf-8") as handle:
                    json.dump(state, handle, indent=2)
            except OSError:
                pass

    def _resolve_config_file(self):
        """Return the primary mock config file path for SBOM provenance.

        Prefers ``config_opts['config_file']`` when set to an existing file.
        This is a path label for forensic context, not a dump of the expanded
        Mock configuration (see ``--debug-config`` / ``--debug-config-expanded``
        on the Mock CLI for that).
        """
        config = self.buildroot.config
        config_file = config.get("config_file")
        if config_file and os.path.isfile(str(config_file)):
            return str(config_file)

        # Fall back to the last non-site file from the include chain.
        paths = list(config.get("config_paths") or [])
        for candidate in reversed(paths):
            if not candidate:
                continue
            base = os.path.basename(candidate)
            if base in ("site-defaults.cfg", "logging.ini"):
                continue
            if os.path.isfile(candidate):
                return candidate

        config_dir = config.get("config_path")
        root = config.get("root") or config.get("chroot_name")
        if config_dir and root:
            candidate = os.path.join(str(config_dir), f"{root}.cfg")
            if os.path.isfile(candidate):
                return candidate
        return None

    def _build_env_snapshot(self):
        """Snapshot Mock network/isolation settings for the SBOM.

        Always records effective isolation / use_nspawn (resolved defaults),
        not only when the keys were explicitly set in config.
        """
        config = self.buildroot.config
        env = {
            "online": bool(config.get("online", True)),
            "rpmbuild_networking": bool(config.get("rpmbuild_networking", False)),
        }
        isolation = config.get("isolation")
        use_nspawn = config.get("use_nspawn")

        # Keep isolation and use_nspawn consistent. Explicit isolation wins;
        # only None/auto derive from Mock's resolved runtime backend.
        if isolation == "simple":
            use_nspawn = False
        elif isolation == "nspawn":
            use_nspawn = True
        else:
            # isolation is None or "auto"
            if use_nspawn is None:
                use_nspawn = bool(mockbuild.util.USE_NSPAWN)
            isolation = "nspawn" if use_nspawn else "simple"

        env["isolation"] = str(isolation)
        env["use_nspawn"] = bool(use_nspawn)
        return env

    @staticmethod
    def _bool_cli(value):
        """Format a boolean for mock-sbom-generator CLI flags."""
        return "true" if value else "false"

    def _prebuild_json_path(self):
        """Return the prebuild JSON path, accepting the legacy hidden name."""
        if os.path.isfile(self.prebuild_state_path):
            return self.prebuild_state_path
        legacy = os.path.join(self.buildroot.resultdir, LEGACY_PREBUILD_STATE_FILENAME)
        if os.path.isfile(legacy):
            return legacy
        return None

    def _inject_host_provenance(self):
        """Capture host forensics + hardening macros on the Mock host.

        Writes ``host_metadata_properties`` and ``hardening_properties`` into
        ``sbom-prebuild.json`` so the generator (which may run in bootstrap)
        does not re-query getenforce/distro/hostname or evaluate macros with
        bootstrap's RPM personality.
        """
        # Late import from the same mockbuild tree this plugin file lives in
        # (plugin_dir / in-tree), not a possibly-stale site-packages copy.
        sbom_generator_cls = self._load_sbom_generator_class()

        path = self._prebuild_json_path() or self.prebuild_state_path
        state = {}
        if path and os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    loaded = json.load(handle)
                if isinstance(loaded, dict):
                    state = loaded
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                self.buildroot.root_log.warning(
                    "[SBOM] Could not load prebuild JSON for host provenance: %s",
                    exc,
                )

        try:
            # Use the live Buildroot so host rpm --root sees the target macros.
            gen = sbom_generator_cls(self.conf, self.buildroot)
            host_props, hardening_props = gen.collect_host_provenance()
            state["host_metadata_properties"] = host_props
            state["hardening_properties"] = hardening_props
            os.makedirs(self.buildroot.resultdir, exist_ok=True)
            with open(self.prebuild_state_path, "w", encoding="utf-8") as handle:
                json.dump(state, handle, indent=2)
            self.buildroot.root_log.debug(
                "[SBOM] Injected %d host + %d hardening properties into %s",
                len(host_props),
                len(hardening_props),
                self.prebuild_state_path,
            )
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self.buildroot.root_log.warning(
                "[SBOM] Failed to capture host provenance for SBOM: %s", exc
            )

    def _command_substitution(self):
        """Build the %-format map for Mock-owned command placeholders.

        Generator-specific flags (``--type``, ``--include-*``, ``--generate-cpe``)
        are not substituted from plugin opts; embed them literally in ``command``.
        """
        env = self._build_env_snapshot()
        return {
            "resultdir": self.buildroot.resultdir,
            "root": self.buildroot.make_chroot_path(),
            "builddir": self.buildroot.builddir,
            "online": self._bool_cli(env["online"]),
            "rpmbuild_networking": self._bool_cli(env["rpmbuild_networking"]),
            "isolation": str(env["isolation"]),
            "use_nspawn": self._bool_cli(env["use_nspawn"]),
        }

    def _build_generator_argv(self):
        """Expand the command template and append optional provenance flags."""
        try:
            formatted = self.command % self._command_substitution()
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                f"Invalid sbom_generator command template: {exc}"
            ) from exc
        cmd = shlex.split(formatted)

        prebuild = self._prebuild_json_path()
        if prebuild:
            cmd.extend(["--prebuild-json", prebuild])

        mock_version = self.buildroot.config.get("version")
        if mock_version:
            cmd.extend(["--mock-version", str(mock_version)])

        config_file = self._resolve_config_file()
        if config_file:
            cmd.extend(["--mock-config", config_file])

        return cmd

    def _path_in_target_root(self, path):
        """Return True if path resolves inside the target buildroot."""
        if not path:
            return False
        try:
            real = os.path.realpath(path)
            target = os.path.realpath(self.buildroot.make_chroot_path())
        except OSError:
            return False
        return real == target or real.startswith(target + os.sep)

    def _host_mockbuild_dir(self):
        """Directory containing the host mockbuild package (trusted source).

        Prefer the package that contains this plugin file so ``plugin_dir`` /
        in-tree testing stages matching modules, not a stale site-packages copy.
        """
        here = os.path.dirname(os.path.realpath(__file__))
        pkg = os.path.dirname(here)
        if os.path.isfile(os.path.join(pkg, "sbom_generate.py")):
            return pkg
        import mockbuild as mockbuild_pkg  # pylint: disable=import-outside-toplevel
        return os.path.dirname(os.path.realpath(mockbuild_pkg.__file__))

    def _host_generator_script(self):
        """Path to the host mock-sbom-generator script."""
        # Prefer the script next to the mockbuild package we will stage (in-tree
        # checkout). Fall back to the packaged /usr/bin path for installed RPMs.
        candidate = os.path.join(
            os.path.dirname(self._host_mockbuild_dir()), "mock-sbom-generator.py"
        )
        if os.path.isfile(candidate):
            return candidate
        if os.path.isfile(DEFAULT_GENERATOR_PATH):
            return DEFAULT_GENERATOR_PATH
        return DEFAULT_GENERATOR_PATH

    def _load_sbom_generator_class(self):
        """Load SBOMGenerator from the same mockbuild tree this plugin uses."""
        import importlib.util  # pylint: disable=import-outside-toplevel

        mod_path = os.path.join(self._host_mockbuild_dir(), "sbom_generate.py")
        spec = importlib.util.spec_from_file_location(
            "mockbuild_sbom_generate_hostinj", mod_path
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load SBOM generator from {mod_path}")
        module = importlib.util.module_from_spec(spec)
        # Ensure sibling mockbuild imports resolve when the module loads.
        pkg_parent = os.path.dirname(self._host_mockbuild_dir())
        if pkg_parent not in sys.path:
            sys.path.insert(0, pkg_parent)
        spec.loader.exec_module(module)
        return module.SBOMGenerator

    def _bootstrap_python_deps(self):
        """Ensure python3 + python3-rpm exist in bootstrap (never the target)."""
        bootstrap = self.buildroot.bootstrap_buildroot
        if not bootstrap:
            return

        need = []
        if not os.path.isfile(bootstrap.make_chroot_path("usr", "bin", "python3")):
            need.append("python3")
        rpm_paths = glob.glob(
            bootstrap.make_chroot_path("usr", "lib*", "python*", "site-packages", "rpm")
        )
        if not rpm_paths:
            need.append("python3-rpm")
        if not need:
            return

        self.buildroot.root_log.info(
            "Installing SBOM generator dependencies into bootstrap: %s",
            ", ".join(need),
        )
        try:
            bootstrap.install_as_root(*need)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self.buildroot.root_log.warning(
                "Failed installing SBOM bootstrap deps %s: %s", need, exc
            )

    def _stage_generator_into_bootstrap(self):
        """Copy the host-trusted generator + modules into bootstrap libexec.

        Returns the in-bootstrap path to the staged script (chroot-absolute).
        """
        bootstrap = self.buildroot.bootstrap_buildroot
        host_pkg = self._host_mockbuild_dir()
        host_script = self._host_generator_script()
        if not os.path.isfile(host_script):
            raise FileNotFoundError(
                f"Host SBOM generator not found at {host_script}"
            )

        stage_root = bootstrap.make_chroot_path(BOOTSTRAP_SBOM_LIBEXEC.lstrip("/"))
        stage_pkg = os.path.join(stage_root, "mockbuild")
        mockbuild.file_util.mkdirIfAbsent(stage_pkg)

        for name in _BOOTSTRAP_MODULE_FILES:
            src = os.path.join(host_pkg, name)
            if not os.path.isfile(src):
                raise FileNotFoundError(f"Missing host mockbuild module: {src}")
            shutil.copy2(src, os.path.join(stage_pkg, name))

        staged_script = bootstrap.make_chroot_path(
            BOOTSTRAP_SBOM_SCRIPT.lstrip("/")
        )
        shutil.copy2(host_script, staged_script)
        os.chmod(staged_script, 0o755)
        self.buildroot.root_log.debug(
            "Staged host-trusted SBOM generator into bootstrap at %s",
            BOOTSTRAP_SBOM_SCRIPT,
        )
        return BOOTSTRAP_SBOM_SCRIPT

    @contextmanager
    def _with_resultdir_in_bootstrap(self):
        """Bind-mount resultdir into bootstrap so the generator can write SBOMs."""
        bootstrap = self.buildroot.bootstrap_buildroot
        resultdir = self.buildroot.resultdir
        if not bootstrap or not resultdir:
            yield
            return
        bootstrap_resultdir = bootstrap.make_chroot_path(resultdir)
        mount = BindMountPoint(resultdir, bootstrap_resultdir, options="private")
        with mount.having_mounted():
            yield

    @contextmanager
    def _with_host_binary_in_bootstrap(self, host_path):
        """Bind-mount a host generator binary into bootstrap at the same path."""
        bootstrap = self.buildroot.bootstrap_buildroot
        if not bootstrap or not host_path or not os.path.isfile(host_path):
            yield
            return
        bindpath = bootstrap.make_chroot_path(host_path)
        mount = BindMountPoint(host_path, bindpath, options="private")
        with mount.having_mounted():
            yield

    def _prepare_bootstrap_argv(self, cmd):
        """Rewrite argv for bootstrap execution; return (argv, host_binds).

        ``host_binds`` is a list of host absolute paths to bind-mount into
        bootstrap for the duration of the run (custom external generators).
        """
        if not cmd:
            raise ValueError("SBOM generator command is empty")

        argv0 = cmd[0]
        if self._path_in_target_root(argv0):
            raise ValueError(
                "SBOM generator command must not point inside the target "
                f"buildroot (refusing {argv0!r} for supply-chain safety)"
            )

        host_binds = []
        use_default = (
            argv0 == DEFAULT_GENERATOR_PATH
            or os.path.realpath(argv0) == os.path.realpath(self._host_generator_script())
        )

        if use_default:
            staged = self._stage_generator_into_bootstrap()
            # env prefix so bootstrap python finds the staged mockbuild package.
            argv = [
                "/usr/bin/env",
                f"PYTHONPATH={BOOTSTRAP_SBOM_LIBEXEC}",
                staged,
            ] + list(cmd[1:])
            return argv, host_binds

        # External generator: bind-mount host binary if it exists on the host.
        if os.path.isabs(argv0) and os.path.isfile(argv0):
            host_binds.append(os.path.realpath(argv0))
        return list(cmd), host_binds

    def _run_sbom_generator_on_host(self, cmd):
        """Run the generator as a host process (bootstrap disabled)."""
        with self.buildroot.uid_manager:
            mockbuild.util.do(cmd, shell=False)

    def _fix_sbom_result_ownership(self):
        """Chown SBOM artifacts in resultdir to the invoking (unprivileged) user.

        Bootstrap ``doOutChroot`` runs as root, so without this the ``*.sbom``
        files are root-owned mode 0600 and unreadable to the Mock caller.
        """
        resultdir = self.buildroot.resultdir
        if not resultdir or not os.path.isdir(resultdir):
            return
        uid = self.buildroot.uid_manager.unprivUid
        gid = self.buildroot.uid_manager.unprivGid
        suffixes = (".sbom", ".sbom.sha256", ".spdx.json")
        for name in os.listdir(resultdir):
            if not name.endswith(suffixes):
                continue
            path = os.path.join(resultdir, name)
            try:
                os.chown(path, uid, gid)
                os.chmod(path, 0o644)
            except OSError as exc:
                self.buildroot.root_log.debug(
                    "Could not fix ownership of %s: %s", path, exc
                )

    def _run_sbom_generator_in_bootstrap(self, cmd):
        """Stage host-trusted tool into bootstrap and run via doOutChroot."""
        with self.buildroot.uid_manager.elevated_privileges():
            self._bootstrap_python_deps()
            argv, host_binds = self._prepare_bootstrap_argv(cmd)
            self.buildroot.root_log.info(
                "Running SBOM generator in bootstrap: %s", " ".join(argv)
            )
            with ExitStack() as stack:
                stack.enter_context(self._with_resultdir_in_bootstrap())
                for host_path in host_binds:
                    stack.enter_context(self._with_host_binary_in_bootstrap(host_path))
                # doOutChroot mounts the target root and runs in bootstrap.
                self.buildroot.doOutChroot(argv, shell=False, printOutput=True)
            self._fix_sbom_result_ownership()

    def _run_sbom_generator(self):
        """Invoke the configured SBOM generator command.

        With bootstrap enabled, the host-trusted generator is copied into
        bootstrap and executed via ``doOutChroot`` (native bootstrap rpm).
        The generator is never installed into or run from the target buildroot.
        When bootstrap is off, the generator runs on the host.
        """
        if self.sbom_done or not self.sbom_enabled:
            return

        state_text = "Generating SBOM for built packages"
        self.state.start(state_text)
        try:
            # Capture host forensics / hardening before bootstrap exec so the
            # generator can prefer injected properties over in-bootstrap queries.
            self._inject_host_provenance()
            cmd = self._build_generator_argv()
            self.buildroot.root_log.debug("Running SBOM generator: %s", " ".join(cmd))
            if self.buildroot.bootstrap_buildroot:
                self._run_sbom_generator_in_bootstrap(cmd)
            else:
                self._run_sbom_generator_on_host(cmd)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            # Best-effort forensic step: never fail the Mock build over SBOM.
            self.buildroot.root_log.warning("SBOM generation failed: %s", exc)
        finally:
            self.sbom_done = True
            # Keep the prebuild snapshot as a forensic artifact in resultdir.
            self.state.finish(state_text)
