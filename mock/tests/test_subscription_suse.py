"""Tests for the SUSE Linux Enterprise subscription support."""

import json
from contextlib import contextmanager
from unittest import mock

import pytest
from mockbuild import exception, subscription_suse

SCC_PRODUCT = {
    "identifier": "SLES",
    "version": "15.7",
    "arch": "x86_64",
    "repositories": [
        {"name": "SLE-Product-SLES15-SP7-Pool", "description": "SLES15-SP7-Pool",
         "url": "https://updates.suse.com/SUSE/Products/SLE-Product-SLES/15-SP7/x86_64/product/?tok3n",
         "enabled": True},
        {"name": "SLE-Product-SLES15-SP7-Debuginfo-Pool", "description": "SLES15-SP7-Debuginfo-Pool",
         "url": "https://updates.suse.com/SUSE/Products/SLE-Product-SLES/15-SP7/x86_64/product_debug/?tok3n",
         "enabled": False},
    ],
    "extensions": [
        {"identifier": "sle-module-basesystem", "recommended": True,
         "repositories": [
             {"name": "SLE-Module-Basesystem15-SP7-Pool", "description": "Basesystem-Pool",
              "url": "https://updates.suse.com/SUSE/Products/SLE-Module-Basesystem/15-SP7/x86_64/product/?b4se",
              "enabled": True},
         ],
         "extensions": [
             {"identifier": "sle-module-development-tools", "recommended": False,
              "repositories": [
                  {"name": "SLE-Module-DevTools15-SP7-Pool", "description": "DevTools-Pool",
                   "url": "https://updates.suse.com/SUSE/Products/SLE-Module-DevTools/15-SP7/x86_64/product/?d3v",
                   "enabled": True},
              ]},
             {"identifier": "sle-ha", "recommended": False, "repositories": [
                 {"name": "SLE-Product-HA15-SP7-Pool", "description": "HA-Pool",
                  "url": "https://updates.suse.com/SUSE/Products/SLE-HA/15-SP7/x86_64/product/?h4",
                  "enabled": True},
             ]},
         ]},
    ],
}


class FakeUidManager:
    """Stand-in for UidManager that does not change privileges."""

    @contextmanager
    def elevated_privileges(self):
        """Do nothing."""
        yield


class FakeResponse:
    """Minimal requests.Response replacement."""

    def __init__(self, status_code, payload):
        self.status_code = status_code
        self.reason = "reason"
        self._payload = payload

    def json(self):
        """Return the payload."""
        return self._payload


def _opts(tmp_path, **kwargs):
    """Return a configuration for SLES 15 SP7 x86_64, overridden by kwargs."""
    opts = {
        "suse_subscription_required": True,
        "suse_subscription_product": "SLES",
        "suse_subscription_version": "15.7",
        "suse_subscription_arch": "x86_64",
        "suse_subscription_extensions": [],
        "suse_subscription_include_recommended": True,
        "suse_subscription_regcode": None,
        "suse_subscription_server": None,
        "suse_subscription_credentials_file": str(tmp_path / "SCCcredentials"),
        "suse_subscription_gpgkey": "file:///key",
        "suse_subscription_repos": "",
        "suse_subscription_bootstrap_extensions": [],
        "suse_subscription_bootstrap_gpgkey": "",
        "use_bootstrap": True,
        "use_bootstrap_image": False,
        "host_arch": "x86_64",
        "target_arch": "x86_64",
        "legal_host_arches": ("x86_64",),
        "repo_arch": "x86_64",
        "repo_arch_map": {},
        "online": True,
        "root": "sles-15.7-x86_64",
        "cache_topdir": str(tmp_path / "cache"),
    }
    opts.update(kwargs)
    return opts


@pytest.fixture(autouse=True)
def no_suseconnect_config(tmp_path, monkeypatch):
    """Never read the /etc/SUSEConnect of the machine running the tests."""
    monkeypatch.setattr(subscription_suse, "SUSECONNECT_CONFIG", str(tmp_path / "SUSEConnect"))


def test_not_required(tmp_path):
    """Configs without SUSE subscription do not contact any server."""
    opts = _opts(tmp_path, suse_subscription_required=False)
    with mock.patch("requests.get") as get:
        subscription_suse.subscription_suse_init(opts, FakeUidManager())
    get.assert_not_called()
    assert opts["suse_subscription_repos"] == ""


def test_not_registered(tmp_path):
    """An unregistered host without registration code gets a helpful error."""
    with pytest.raises(exception.ConfigError, match="not registered"):
        subscription_suse.subscription_suse_init(_opts(tmp_path), FakeUidManager())


def test_regcode(tmp_path):
    """A registration code gives the base product, recommended and requested repositories."""
    opts = _opts(tmp_path, suse_subscription_regcode="REGCODE",
                 suse_subscription_extensions=["sle-module-development-tools"])
    with mock.patch("requests.get", return_value=FakeResponse(200, SCC_PRODUCT)) as get:
        subscription_suse.subscription_suse_init(opts, FakeUidManager())

    get.assert_called_once()
    args, kwargs = get.call_args
    assert args[0] == "https://scc.suse.com/connect/subscriptions/products"
    assert kwargs["headers"] == {"Authorization": "Token token=REGCODE"}
    assert kwargs["params"] == {"identifier": "SLES", "version": "15.7", "arch": "x86_64"}

    repos = opts["suse_subscription_repos"]
    assert "[SLE-Product-SLES15-SP7-Pool]" in repos
    assert "baseurl=https://updates.suse.com/SUSE/Products/SLE-Product-SLES/15-SP7/x86_64/product/?tok3n" in repos
    assert "[SLE-Product-SLES15-SP7-Debuginfo-Pool]\nname=SLES15-SP7-Debuginfo-Pool\n" in repos
    assert "[SLE-Module-Basesystem15-SP7-Pool]" in repos  # recommended
    assert "[SLE-Module-DevTools15-SP7-Pool]" in repos  # requested
    assert "HA15" not in repos
    assert "gpgkey=file:///key" in repos
    assert "username=" not in repos


def test_disabled_repo_stays_disabled(tmp_path):
    """Repositories disabled by the server (debuginfo, source) stay disabled."""
    opts = _opts(tmp_path, suse_subscription_regcode="REGCODE")
    with mock.patch("requests.get", return_value=FakeResponse(200, SCC_PRODUCT)):
        subscription_suse.subscription_suse_init(opts, FakeUidManager())
    section = opts["suse_subscription_repos"].split("[SLE-Product-SLES15-SP7-Debuginfo-Pool]")[1]
    assert section.split("\n\n")[0].count("enabled=0") == 1


def test_no_recommended(tmp_path):
    """Recommended extensions can be left out."""
    opts = _opts(tmp_path, suse_subscription_regcode="REGCODE",
                 suse_subscription_include_recommended=False)
    with mock.patch("requests.get", return_value=FakeResponse(200, SCC_PRODUCT)):
        subscription_suse.subscription_suse_init(opts, FakeUidManager())
    assert "Basesystem" not in opts["suse_subscription_repos"]


def test_unknown_extension(tmp_path):
    """Requesting an unknown extension lists the available ones."""
    opts = _opts(tmp_path, suse_subscription_regcode="REGCODE",
                 suse_subscription_extensions=["sle-module-nope"])
    with mock.patch("requests.get", return_value=FakeResponse(200, SCC_PRODUCT)), \
            pytest.raises(exception.ConfigError) as err:
        subscription_suse.subscription_suse_init(opts, FakeUidManager())
    assert "sle-module-nope" in str(err.value)
    assert "sle-module-development-tools" in str(err.value)


def test_scc_registered_system(tmp_path):
    """A host registered with SCC uses its first working, non-expired regcode."""
    (tmp_path / "SCCcredentials").write_text("username=SCC_user\npassword=secret\nsystem_token=tok\n")
    opts = _opts(tmp_path)

    def fake_get(url, **kwargs):
        if url.endswith("/connect/systems/subscriptions"):
            assert kwargs["auth"] == ("SCC_user", "secret")
            assert kwargs["headers"] == {"System-Token": "tok"}
            return FakeResponse(200, [{"regcode": "OLD", "status": "EXPIRED"},
                                      {"regcode": "BAD", "status": "ACTIVE"},
                                      {"regcode": "GOOD", "status": "ACTIVE"}])
        if kwargs["headers"]["Authorization"] == "Token token=BAD":
            return FakeResponse(422, {"error": "No product found"})
        assert kwargs["headers"]["Authorization"] == "Token token=GOOD"
        return FakeResponse(200, [SCC_PRODUCT])

    with mock.patch("requests.get", side_effect=fake_get) as get:
        subscription_suse.subscription_suse_init(opts, FakeUidManager())
    assert get.call_count == 3
    assert "[SLE-Product-SLES15-SP7-Pool]" in opts["suse_subscription_repos"]
    # SCC URLs carry a CDN token, the system credentials must not leak into dnf.conf.
    assert "secret" not in opts["suse_subscription_repos"]


def test_no_valid_subscription(tmp_path):
    """A host with only expired subscriptions gets an error."""
    (tmp_path / "SCCcredentials").write_text("username=SCC_user\npassword=secret\n")
    opts = _opts(tmp_path)
    with mock.patch("requests.get", return_value=FakeResponse(200, [{"regcode": "X", "status": "EXPIRED"}])), \
            pytest.raises(exception.ConfigError, match="expired"):
        subscription_suse.subscription_suse_init(opts, FakeUidManager())


def test_product_not_available(tmp_path):
    """The error reported by the server is shown to the user."""
    opts = _opts(tmp_path, suse_subscription_regcode="REGCODE")
    with mock.patch("requests.get", return_value=FakeResponse(422, {"error": "No product found"})), \
            pytest.raises(exception.ConfigError, match="No product found"):
        subscription_suse.subscription_suse_init(opts, FakeUidManager())


def test_rmt(tmp_path):
    """RMT uses the system credentials both for the API and the repositories."""
    (tmp_path / "SCCcredentials").write_text("username=SCC_user\npassword=secret\n")
    (tmp_path / "SUSEConnect").write_text("---\nurl: https://rmt.example.com/\ninsecure: true\n")
    opts = _opts(tmp_path)
    product = {
        "identifier": "SLES",
        "repositories": [
            {"name": "SLES-Pool", "enabled": True,
             "url": "https://rmt.example.com/repo/SUSE/Products/SLE-Product-SLES/15-SP7/x86_64/product"
                    "?credentials=SCCcredentials"},
        ],
    }

    def fake_get(url, **kwargs):
        assert kwargs["verify"] is False
        if url == "https://rmt.example.com/connect/systems/subscriptions":
            return FakeResponse(404, None)
        assert url == "https://rmt.example.com/connect/systems/products"
        assert kwargs["auth"] == ("SCC_user", "secret")
        return FakeResponse(200, product)

    with mock.patch("requests.get", side_effect=fake_get):
        subscription_suse.subscription_suse_init(opts, FakeUidManager())

    repos = opts["suse_subscription_repos"]
    assert "baseurl=https://rmt.example.com/repo/SUSE/Products/SLE-Product-SLES/15-SP7/x86_64/product\n" in repos
    assert "username=SCC_user\npassword=secret" in repos
    assert "name=SLES-Pool" in repos


def test_connection_error(tmp_path):
    """Network errors are reported as configuration errors."""
    opts = _opts(tmp_path, suse_subscription_regcode="REGCODE",
                 suse_subscription_server="https://scc.example.com")
    error = subscription_suse.requests.ConnectionError("boom")
    with mock.patch("requests.get", side_effect=error), \
            pytest.raises(exception.ConfigError, match="scc.example.com.*boom"):
        subscription_suse.subscription_suse_init(opts, FakeUidManager())


def test_already_initialized(tmp_path):
    """Repositories set on the command line are not looked up again."""
    opts = _opts(tmp_path, suse_subscription_repos="[cached]")
    with mock.patch("requests.get") as get:
        subscription_suse.subscription_suse_init(opts, FakeUidManager())
    get.assert_not_called()


def test_bootstrap_extensions(tmp_path):
    """Bootstrap-only extensions are added to the bootstrap repositories only."""
    opts = _opts(tmp_path, suse_subscription_regcode="REGCODE",
                 suse_subscription_bootstrap_extensions=["sle-module-development-tools"],
                 suse_subscription_bootstrap_gpgkey="file:///hub")
    with mock.patch("requests.get", return_value=FakeResponse(200, SCC_PRODUCT)):
        subscription_suse.subscription_suse_init(opts, FakeUidManager())

    assert "DevTools" not in opts["suse_subscription_repos"]
    bootstrap = opts["bootstrap_suse_subscription_repos"]
    assert bootstrap.startswith(opts["suse_subscription_repos"])
    assert bootstrap.count("[SLE-Module-Basesystem15-SP7-Pool]") == 1
    devtools = bootstrap.split("[SLE-Module-DevTools15-SP7-Pool]")[1]
    assert "gpgkey=file:///key file:///hub" in devtools
    assert "file:///hub" not in bootstrap.split("[SLE-Module-DevTools15-SP7-Pool]")[0]


def _product_for_arch(arch):
    """Return a copy of SCC_PRODUCT with URLs of the given architecture."""
    return json.loads(json.dumps(SCC_PRODUCT).replace("x86_64", arch))


def test_bootstrap_emulated_target(tmp_path):
    """An emulated target gets a host-native bootstrap, with host repositories."""
    opts = _opts(tmp_path, suse_subscription_regcode="REGCODE", suse_subscription_arch="aarch64",
                 target_arch="aarch64", legal_host_arches=("aarch64",), repo_arch="aarch64",
                 suse_subscription_bootstrap_extensions=["sle-module-development-tools"])

    def fake_get(_url, **kwargs):
        return FakeResponse(200, _product_for_arch(kwargs["params"]["arch"]))

    with mock.patch("requests.get", side_effect=fake_get) as get:
        subscription_suse.subscription_suse_init(opts, FakeUidManager())

    # call.kwargs needs Python 3.8
    assert [kwargs["params"]["arch"] for _, kwargs in get.call_args_list] == ["aarch64", "x86_64"]
    assert "x86_64" not in opts["suse_subscription_repos"]
    assert "DevTools" not in opts["suse_subscription_repos"]
    bootstrap = opts["bootstrap_suse_subscription_repos"]
    assert "aarch64" not in bootstrap
    assert "SLE-Module-DevTools/15-SP7/x86_64" in bootstrap


def test_bootstrap_emulated_no_extensions(tmp_path):
    """Host repositories are needed for an emulated target even without extra extensions."""
    opts = _opts(tmp_path, suse_subscription_regcode="REGCODE", suse_subscription_arch="aarch64",
                 target_arch="aarch64", legal_host_arches=("aarch64",), repo_arch="aarch64")

    def fake_get(_url, **kwargs):
        return FakeResponse(200, _product_for_arch(kwargs["params"]["arch"]))

    with mock.patch("requests.get", side_effect=fake_get):
        subscription_suse.subscription_suse_init(opts, FakeUidManager())
    assert "aarch64" not in opts["bootstrap_suse_subscription_repos"]
    assert "SLE-Product-SLES/15-SP7/x86_64" in opts["bootstrap_suse_subscription_repos"]


def test_no_bootstrap(tmp_path):
    """Without bootstrap chroot, only the target repositories are requested."""
    opts = _opts(tmp_path, suse_subscription_regcode="REGCODE", use_bootstrap=False,
                 suse_subscription_bootstrap_extensions=["sle-module-development-tools"])
    with mock.patch("requests.get", return_value=FakeResponse(200, SCC_PRODUCT)) as get:
        subscription_suse.subscription_suse_init(opts, FakeUidManager())
    get.assert_called_once()
    assert "bootstrap_suse_subscription_repos" not in opts


def test_native_target_single_request(tmp_path):
    """A native target reuses the product tree for the bootstrap repositories."""
    opts = _opts(tmp_path, suse_subscription_regcode="REGCODE",
                 suse_subscription_bootstrap_extensions=["sle-module-development-tools"])
    with mock.patch("requests.get", return_value=FakeResponse(200, SCC_PRODUCT)) as get:
        subscription_suse.subscription_suse_init(opts, FakeUidManager())
    get.assert_called_once()


def test_offline_reuses_stored_repositories(tmp_path):
    """An online run stores the repositories, an offline run reuses them without requests."""
    opts = _opts(tmp_path, suse_subscription_regcode="REGCODE",
                 suse_subscription_bootstrap_extensions=["sle-module-development-tools"])
    with mock.patch("requests.get", return_value=FakeResponse(200, SCC_PRODUCT)):
        subscription_suse.subscription_suse_init(opts, FakeUidManager())
    stored = tmp_path / "cache" / "sles-15.7-x86_64" / "suse_subscription_repos.json"
    assert stored.stat().st_mode & 0o777 == 0o600

    offline = _opts(tmp_path, online=False)
    with mock.patch("requests.get") as get:
        subscription_suse.subscription_suse_init(offline, FakeUidManager())
    get.assert_not_called()
    assert offline["suse_subscription_repos"] == opts["suse_subscription_repos"]
    assert offline["bootstrap_suse_subscription_repos"] == opts["bootstrap_suse_subscription_repos"]


def test_offline_without_stored_repositories(tmp_path):
    """Offline mode fails clearly if no online run stored the repositories."""
    with mock.patch("requests.get") as get:
        with pytest.raises(exception.ConfigError, match="run mock online once first"):
            subscription_suse.subscription_suse_init(_opts(tmp_path, online=False), FakeUidManager())
    get.assert_not_called()
