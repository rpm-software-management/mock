# Mock Project Contributing Guidelines 

# Key Principles
* **Readability:** Code should be easy to understand for all team members.
* **Maintainability:** Code should be easy to modify and extend.
* **Consistency:** Adhering to a consistent style across all projects improves
  collaboration and reduces errors.
* **Compatibility:** Code should run on both new and old Linux platforms. Including Fedora rawhide, all supported RHELs, openSUSE etc.
* **AI Contributions:** Commits done with the help of AI should have in commit description: "Assisted-By: AGENT-NAME"

## Naming Conventions

* **Variables:** Use lowercase with underscores (snake_case): `user_name`, `total_count`
* **Constants:**  Use uppercase with underscores: `MAX_VALUE`, `DATABASE_NAME`
* **Functions:** Use lowercase with underscores (snake_case): `calculate_total()`, `process_data()`
* **Classes:** Use CapWords (CamelCase): `UserManager`, `PaymentProcessor`
* **Modules:** Use lowercase with underscores (snake_case): `user_utils`, `payment_gateway`
* **Line length**: 120 characters
* **Plugin architecture**: Plugins are hook-based; configurations flow through `config_opts` dict

## Docstrings
* **Use triple double quotes (`"""Docstring goes here."""`) for all docstrings.**
* **First line:** Concise summary of the object's purpose.
* **For complex functions/classes:** Include detailed descriptions of parameters, return values,
  attributes, and exceptions.
* **Use Google style docstrings:** This helps with automated documentation generation.
    ```python
    def my_function(param1, param2):
        """Single-line summary.

        More detailed description, if necessary.

        Args:
            param1 (int): The first parameter.
            param2 (str): The second parameter.

        Returns:
            bool: The return value. True for success, False otherwise.

        Raises:
            ValueError: If `param2` is invalid.
        """
        # function body here
    ```

## Comments
* **Write clear and concise comments:** Explain the "why" behind the code, not just the "what".
* **Comment sparingly:** Well-written code should be self-documenting where possible.
* **Use complete sentences:** Start comments with a capital letter and use proper punctuation.

# Tooling
* **Internal utils:**  The file `mock/py/mockbuild/util.py` contains several helper functions that helps with compatibility. The code should use these functions when possible instead standard Python functions.


## Build & Release

Releases use **Tito** (git-based release tool):
* `tito build --rpm` — build binary RPM from the lastest tagged release
* `tito build --srpm` — build source RPM from the lastest tagged release
* `tito build --test --rpm` — test build from from the latest commit

Version is defined in `mock/mock.spec`. At install time, the Makefile substitutes `__VERSION__`, `SYSCONFDIR`, `PYTHONDIR`, etc. in source files via `install-exec-hook`.

## Testing

**Unit tests** (pytest):
```bash
# Via tox (preferred, tests across Python 3.9–3.13):
tox

# Direct (from repo root):
cd mock && ./run-tests.sh

# Single test:
PYTHONPATH=./mock/py python -m pytest mock/tests/test_config_loader.py -v

# Without coverage:
cd mock && ./run-tests.sh --no-cov
```

Coverage enforcement: 100% coverage required for `mock/py/mockbuild/plugins/rpmautospec.py`.

**Integration tests** (shell scripts, require mock installed): `cd mock && make check`

**BDD tests** (behave, in `behave/`): require an isolated/disposable machine — they can destroy your system.

## Linting

CI runs `ruff` and `pylint` via `vcs-diff-lint-action` on diffs against main. Configs:
* Pylint: `mock/pylintrc`, `behave/pylintrc`
* Flake8: `mock/setup.cfg` (max line length 120, google import order)

## Architecture

```
CLI (mock/py/mock.py, mockchain)
 → Config (config.py — loads/templates TemplatedDictionary configs from /etc/mock/)
 → Backend (backend.py — orchestrates RPM build commands)
 → Buildroot (buildroot.py — chroot lifecycle, mounts, package installation)
 → Package Manager (package_manager.py — abstraction over DNF5/DNF4/YUM/microDNF)
 → Plugin System (plugin.py + ~24 plugins in mockbuild/plugins/)
 → Utilities (util.py — subprocess, namespaces, compat helpers)
```

All Python source lives under `mock/py/`. The `mockbuild/` package is the core library; `mock.py` is the CLI entry point.

Key directories:
* `mock-core-configs/` — separate package providing per-distro/arch configuration files
* `behave/` — BDD test suite (gherkin features + step definitions)
* `releng/` — release engineering tools, towncrier release notes fragments
* `docs/` — Jekyll-based documentation site

## Release Notes

Uses Towncrier. Add fragments to `releng/release-notes-next/` with types: `breaking`, `feature`, `bugfix`, `config`.
