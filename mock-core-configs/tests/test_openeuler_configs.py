"""
Tests for the openEuler chroot templates shipped in mock-core-configs.

The openEuler metalink service exposes source repos only via the
``path=openeuler/<dir>/...`` form.  Unlike the ``repo=`` form, ``path=`` does
*not* translate the ``$releasever`` dnf variable into the full mirror
directory name (e.g. ``24.03LTS_SP4`` -> ``openEuler-24.03-LTS-SP4``), so a
source metalink that relies on ``$releasever`` resolves to a non-existent
path and silently breaks ``mock --sources``.

These tests parse the shipped templates directly (no mock runtime, no
network) and assert that no ``path=`` metalink depends on ``$releasever``.
"""

import os

import pytest

# The tests live in mock-core-configs/tests/, the templates in
# mock-core-configs/etc/mock/templates/.
TEMPLATE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
    "etc", "mock", "templates",
)

OPENEULER_TEMPLATES = [
    f for f in os.listdir(TEMPLATE_DIR)
    if f.startswith("openeuler-") and f.endswith(".tpl")
]


@pytest.mark.parametrize("template", [pytest.param(t, id=t) for t in OPENEULER_TEMPLATES])
def test_path_metalink_does_not_use_releasever(template):
    """``path=`` metalinks must not depend on ``$releasever``.

    The metalink ``path=`` form is taken literally and is never translated,
    so a ``$releasever`` in it would point at a path that does not exist.
    """
    with open(os.path.join(TEMPLATE_DIR, template), encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped.startswith("metalink=") or "path=" not in stripped:
                continue
            assert "$releasever" not in line, (
                f"{template}: source metalink uses the untranslated "
                f"$releasever in a path= form, which the metalink service "
                f"does not translate:\n  {stripped}"
            )
