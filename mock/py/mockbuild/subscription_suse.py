# vim: noai:ts=4:sw=4:expandtab
"""Access to SUSE Linux Enterprise repositories through the SUSE Customer Center.

SUSE does not publish static repository URLs for SUSE Linux Enterprise.
The repositories a subscription grants access to are obtained from the
registration server (SCC, or a local RMT/SMT mirror), which returns the list
of repositories for a given product, version and architecture.  For SCC the
returned URLs carry a short-lived CDN access token in their query string, so
they are requested again on every mock run instead of being stored in the
configuration.

This mirrors what SUSE's own container-suseconnect does to give containers
access to the host's entitlements:

    https://github.com/SUSE/container-suseconnect

The result is stored in config_opts['suse_subscription_repos'] as a block of
dnf repository sections that the SLES templates include in their dnf.conf.
It is also saved in the cache directory of the chroot, and reused in offline
mode, where the registration server is not contacted.
"""

import json
import os
import tempfile
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests

from . import config, exception, file_util

DEFAULT_SERVER = "https://scc.suse.com"
SUSECONNECT_CONFIG = "/etc/SUSEConnect"
REQUEST_TIMEOUT = 60
REPOS_CACHE_FILE = "suse_subscription_repos.json"
REPOS_OPTIONS = ("suse_subscription_repos", "bootstrap_suse_subscription_repos")


def _parse_key_value(text, separator):
    """Parse simple "key<separator>value" files like SCCcredentials or SUSEConnect.

    Args:
        text (str): The file content.
        separator (str): The character separating keys from values.

    Returns:
        dict: The parsed keys and values, both stripped of whitespace.
    """
    result = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or separator not in line:
            continue
        key, value = line.split(separator, 1)
        result[key.strip()] = value.strip()
    return result


def _unquote(value):
    """Remove the quotes around a YAML scalar, like "https://rmt.example.com"."""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def _read_server(opts):
    """Return the registration server URL and whether to verify its TLS certificate.

    The "insecure" setting of /etc/SUSEConnect only applies to the server set
    there, never to config_opts['suse_subscription_server'] or to SCC.
    """
    server = opts["suse_subscription_server"]
    if server or not os.path.exists(SUSECONNECT_CONFIG):
        return (server or DEFAULT_SERVER).rstrip("/"), True
    with open(SUSECONNECT_CONFIG, encoding="utf-8") as config_file:
        data = {key: _unquote(value) for key, value in _parse_key_value(config_file.read(), ":").items()}
    if not data.get("url"):
        return DEFAULT_SERVER, True
    return data["url"].rstrip("/"), data.get("insecure", "false").lower() != "true"


def _read_credentials(opts, uid_manager):
    """Read the system credentials written by SUSEConnect when registering a system.

    The file is only readable by root, hence the elevated privileges.

    Returns:
        dict: The "username", "password" and optional "system_token" keys, or
        None if the credentials file does not exist.
    """
    path = opts["suse_subscription_credentials_file"]
    with uid_manager.elevated_privileges():
        if not os.path.exists(path):
            return None
        with open(path, encoding="utf-8") as credentials_file:
            credentials = _parse_key_value(credentials_file.read(), "=")
    if not credentials.get("username") or not credentials.get("password"):
        raise exception.ConfigError(
            f"{path} does not contain a username and a password")
    return credentials


def _error_detail(response):
    """Extract a human readable error from a registration server response."""
    try:
        payload = response.json()
        if isinstance(payload, dict) and isinstance(payload.get("error"), str) and payload["error"]:
            return payload["error"]
    except ValueError:
        pass
    return f"HTTP {response.status_code} {response.reason}"


def _json(response, server, what):
    """Decode a registration server response.

    Raises:
        ConfigError: If the response is not valid JSON.
    """
    try:
        return response.json()
    except ValueError as err:
        raise exception.ConfigError(f"{server} returned an invalid response for {what}: {err}") from err


def _get(url, verify, auth=None, headers=None, params=None):
    try:
        return requests.get(url, auth=auth, headers=headers, params=params,
                            verify=verify, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as err:
        raise exception.ConfigError(
            f"Can not contact the SUSE registration server {url}: {err}")


def _system_auth(credentials):
    auth = (credentials["username"], credentials["password"])
    headers = {}
    if credentials.get("system_token"):
        headers["System-Token"] = credentials["system_token"]
    return auth, headers


def _request_regcodes(server, verify, credentials):
    """Ask the registration server for the registration codes of a registered system.

    Returns:
        list: The non-expired registration codes, or None if the server does
        not implement the endpoint, which is the case for RMT and SMT.
    """
    auth, headers = _system_auth(credentials)
    response = _get(server + "/connect/systems/subscriptions", verify,
                    auth=auth, headers=headers)
    if response.status_code == 404:
        return None
    if response.status_code != 200:
        raise exception.ConfigError(
            f"Can not retrieve the subscriptions of this system from {server}: {_error_detail(response)}")
    subscriptions = _json(response, server, "the subscriptions of this system")
    if not isinstance(subscriptions, list) or not all(isinstance(sub, dict) for sub in subscriptions):
        raise exception.ConfigError(f"{server} returned an invalid list of subscriptions for this system")
    return [sub["regcode"] for sub in subscriptions
            if isinstance(sub.get("regcode"), str) and sub["regcode"]
            and str(sub.get("status", "")).upper() != "EXPIRED"]


def _parse_product(response, server, product_query):
    """Return the product from a products response, which can be an object or a list."""
    product_name = _product_name(product_query)
    data = _json(response, server, product_name)
    if isinstance(data, list):
        data = data[0] if data else None
    if not data:
        raise exception.ConfigError(f"{server} returned no product for {product_name}")
    if not isinstance(data, dict):
        raise exception.ConfigError(f"{server} returned an invalid product for {product_name}")
    return data


def _request_product(server, verify, product_query, regcodes, credentials):
    """Retrieve the product tree, including all of its extensions and repositories.

    Args:
        server (str): Registration server URL.
        verify (bool): Whether to verify the server TLS certificate.
        product_query (dict): The "identifier", "version" and "arch" of the product.
        regcodes (list): Registration codes to try in order.  If None, the
            system credentials are used directly (RMT and SMT).
        credentials (dict): System credentials, only used if regcodes is None.

    Returns:
        dict: The product as returned by the registration server.
    """
    if regcodes is None:
        auth, headers = _system_auth(credentials)
        response = _get(server + "/connect/systems/products", verify,
                        auth=auth, headers=headers, params=product_query)
        if response.status_code == 200:
            return _parse_product(response, server, product_query)
        errors = [_error_detail(response)]
    else:
        errors = []
        for regcode in regcodes:
            response = _get(server + "/connect/subscriptions/products", verify,
                            headers={"Authorization": "Token token=" + regcode},
                            params=product_query)
            if response.status_code == 200:
                return _parse_product(response, server, product_query)
            errors.append(_error_detail(response))

    product_name = _product_name(product_query)
    reason = "; ".join(errors) or "no active subscription found"
    raise exception.ConfigError(f"No subscription gives access to {product_name}: {reason}")


def _product_name(product_query):
    return f"{product_query['identifier']} {product_query['version']} {product_query['arch']}"


def _walk_products(product):
    """Yield the product and, recursively, all of its extensions."""
    if (not isinstance(product, dict)
            or not isinstance(product.get("identifier"), (str, type(None)))
            or not isinstance(product.get("extensions") or [], list)
            or not isinstance(product.get("repositories") or [], list)):
        raise exception.ConfigError("The SUSE registration server returned an invalid product tree")
    yield product
    for extension in product.get("extensions") or []:
        yield from _walk_products(extension)


def _check_repository(repo, identifier):
    """Make sure a repository has the fields needed to render it.

    The repository is not shown in the error, as its URL carries an access token.
    """
    if not isinstance(repo, dict) or not all(isinstance(repo.get(key), str) and repo[key]
                                             for key in ("name", "url")):
        raise exception.ConfigError(
            f"The SUSE registration server returned an invalid repository for {identifier}")


def _select_repositories(product, extensions, include_recommended):
    """Return the repositories of the base product and of the selected extensions.

    Raises:
        ConfigError: If a requested extension does not exist for the product.
    """
    repositories = []
    seen_repos = set()
    seen_extensions = set()
    available = set()
    for index, item in enumerate(_walk_products(product)):
        identifier = item.get("identifier")
        if index:
            available.add(identifier)
            wanted = identifier in extensions or (include_recommended and item.get("recommended"))
            if not wanted:
                continue
            seen_extensions.add(identifier)
        for repo in item.get("repositories") or []:
            _check_repository(repo, identifier)
            # The same module can appear as extension of several products.
            if repo["name"] in seen_repos:
                continue
            seen_repos.add(repo["name"])
            repositories.append(repo)

    missing = [ext for ext in extensions if ext not in seen_extensions]
    if missing:
        raise exception.ConfigError(
            f"Extension(s) {', '.join(missing)} not available for "
            f"{product.get('identifier')} {product.get('version')}.  "
            f"Available extensions: {', '.join(sorted(ext for ext in available if ext))}")
    return repositories


def _repository_auth(url, credentials):
    """Turn zypper's "?credentials=NAME" URL parameter into dnf basic authentication.

    RMT and SMT do not use CDN tokens but expect the system credentials to be
    sent with HTTP basic authentication; zypper does that when the URL carries a
    "credentials" query parameter.

    Returns:
        tuple: The URL without the "credentials" parameter and the
        (username, password) tuple to use, or None.
    """
    parts = urlsplit(url)
    query = parse_qsl(parts.query, keep_blank_values=True)
    filtered = [(key, value) for key, value in query if key != "credentials"]
    if credentials is None or len(filtered) == len(query):
        return url, None
    url = urlunsplit(parts._replace(query=urlencode(filtered)))
    return url, (credentials["username"], credentials["password"])


def _format_repositories(repositories, gpgkey, credentials):
    """Render the selected repositories as dnf.conf sections."""
    sections = []
    for repo in repositories:
        url, auth = _repository_auth(repo["url"], credentials)
        lines = [
            f"[{repo['name']}]",
            f"name={repo.get('description') or repo['name']}",
            f"baseurl={url}",
            f"enabled={1 if repo.get('enabled') else 0}",
            "sslverify=1",
            "skip_if_unavailable=False",
        ]
        if gpgkey:
            lines += ["gpgcheck=1", f"gpgkey={gpgkey}"]
        if auth:
            lines += [f"username={auth[0]}", f"password={auth[1]}"]
        sections.append("\n".join(lines) + "\n")
    return "\n".join(sections)


def _product_repositories(opts, product, extra_extensions, credentials):
    """Render the repositories of a product as dnf.conf sections.

    Args:
        opts (dict): The mock configuration.
        product (dict): The product as returned by the registration server.
        extra_extensions (list): Extensions only wanted in this chroot (e.g.
            Package Hub, the only source of dnf, for the bootstrap chroot).
            Their repositories also accept the suse_subscription_bootstrap_gpgkey
            keys.
        credentials (dict): System credentials for basic authentication, or None.

    Returns:
        str: The dnf.conf repository sections.
    """
    extensions = opts["suse_subscription_extensions"]
    include_recommended = opts["suse_subscription_include_recommended"]
    gpgkey = opts["suse_subscription_gpgkey"]
    base = _select_repositories(product, extensions, include_recommended)
    sections = [_format_repositories(base, gpgkey, credentials)]
    if extra_extensions:
        base_names = {repo["name"] for repo in base}
        extra = [repo for repo in _select_repositories(product, extensions + extra_extensions, include_recommended)
                 if repo["name"] not in base_names]
        extra_gpgkey = " ".join(key for key in (gpgkey, opts["suse_subscription_bootstrap_gpgkey"]) if key)
        sections.append(_format_repositories(extra, extra_gpgkey, credentials))
    return "\n".join(sections)


def _repos_cache_path(opts):
    """Return the file storing the repositories of the last online run."""
    return os.path.join(opts["cache_topdir"], opts["root"], REPOS_CACHE_FILE)


def _bootstrap_needs_own_repositories(opts):
    """Return whether the bootstrap chroot needs repositories different from the target.

    That is the case when the bootstrap needs more extensions (Package Hub, the
    only source of dnf) or when its architecture differs from the target one,
    because the bootstrap chroot is host-native also when the target is emulated
    with --forcearch, and the repository URLs are architecture specific.
    """
    if not opts["use_bootstrap"]:
        return False
    return bool(opts["suse_subscription_bootstrap_extensions"]) \
        or config.get_bootstrap_repo_arch(opts) != opts["suse_subscription_arch"]


def _read_repositories(path):
    """Read the stored repositories, or return None if none were stored.

    Raises:
        ConfigError: If the file is not a valid repository store.
    """
    try:
        with open(path, encoding="utf-8") as repos_file:
            repos = json.load(repos_file)
    except FileNotFoundError:
        return None
    except ValueError as err:
        raise exception.ConfigError(f"{path} is corrupted, run mock online to recreate it: {err}") from err
    if not isinstance(repos, dict) or not all(isinstance(repos.get(key, ""), str) for key in REPOS_OPTIONS):
        raise exception.ConfigError(f"{path} is corrupted, run mock online to recreate it")
    return repos


def _save_repositories(opts, uid_manager):
    """Store the generated repositories for offline runs.

    The repositories carry access tokens or the system credentials, so the
    file is only readable by root.  It is replaced atomically, so offline runs
    never see a partially written file.  A run without bootstrap chroot keeps
    the bootstrap repositories stored by the previous run.

    Args:
        opts (dict): The mock configuration.
        uid_manager (UidManager): Used to write into the root-owned cache.
    """
    path = _repos_cache_path(opts)
    bootstrap_key = REPOS_OPTIONS[1]
    with uid_manager.elevated_privileges():
        repos = {key: opts[key] for key in REPOS_OPTIONS if key in opts}
        if not opts["use_bootstrap"]:
            try:
                previous = _read_repositories(path) or {}
            except exception.ConfigError:
                previous = {}
            if bootstrap_key in previous:
                repos[bootstrap_key] = previous[bootstrap_key]
        directory = os.path.dirname(path)
        file_util.mkdirIfAbsent(directory)
        # mkstemp creates the file with mode 0600.
        fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=f".{REPOS_CACHE_FILE}.")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as repos_file:
                json.dump(repos, repos_file, indent=2)
                repos_file.write("\n")
            os.replace(tmp_path, path)
        except BaseException:
            os.unlink(tmp_path)
            raise


def _load_repositories(opts, uid_manager):
    """Restore the repositories stored by the last online run.

    Args:
        opts (dict): The mock configuration.
        uid_manager (UidManager): Used to read the root-only file.

    Raises:
        ConfigError: If no online run stored the needed repositories yet.
    """
    path = _repos_cache_path(opts)
    with uid_manager.elevated_privileges():
        repos = _read_repositories(path)
    if not repos or REPOS_OPTIONS[0] not in repos:
        raise exception.ConfigError(
            f"Offline mode, but no SUSE repositories were stored in {path}: "
            "run mock online once first")
    opts[REPOS_OPTIONS[0]] = repos[REPOS_OPTIONS[0]]
    if not _bootstrap_needs_own_repositories(opts):
        return
    if REPOS_OPTIONS[1] not in repos:
        raise exception.ConfigError(
            f"Offline mode, but no SUSE repositories for the bootstrap chroot were stored in {path}: "
            "run mock online once first with the bootstrap chroot enabled")
    opts[REPOS_OPTIONS[1]] = repos[REPOS_OPTIONS[1]]


def subscription_suse_init(opts, uid_manager):
    """Fill config_opts['suse_subscription_repos'] for configs that need a SUSE subscription.

    Access is granted either by a registration code configured in
    config_opts['suse_subscription_regcode'], or by the system credentials of
    a host registered with SUSEConnect (SCC, RMT or SMT).  In offline mode,
    the repositories stored by the last online run are used instead.

    Args:
        opts (dict): The mock configuration.
        uid_manager (UidManager): Used to read the root-only credentials file,
            and to store or restore the repositories in the cache.

    Raises:
        ConfigError: If no subscription is available, the registration
            server does not return the requested product, or no online run
            stored the repositories for offline mode.
    """
    if not opts["suse_subscription_required"] or opts["suse_subscription_repos"]:
        return

    if not opts["online"]:
        _load_repositories(opts, uid_manager)
        return

    _request_repositories(opts, uid_manager)
    _save_repositories(opts, uid_manager)


def _request_repositories(opts, uid_manager):
    """Request the repositories from the registration server.

    Args:
        opts (dict): The mock configuration.
        uid_manager (UidManager): Used to read the root-only credentials file.

    Raises:
        ConfigError: If no subscription is available or the registration
            server does not return the requested product.
    """
    server, verify = _read_server(opts)
    product_query = {
        "identifier": opts["suse_subscription_product"],
        "version": opts["suse_subscription_version"],
        "arch": opts["suse_subscription_arch"],
    }

    credentials = None
    regcode = opts["suse_subscription_regcode"]
    if regcode:
        regcodes = [regcode]
    else:
        credentials = _read_credentials(opts, uid_manager)
        if credentials is None:
            credentials_file = opts["suse_subscription_credentials_file"]
            raise exception.ConfigError(
                f"This system is not registered with the SUSE Customer Center: {credentials_file} "
                "does not exist.  Either register it with\n"
                "  SUSEConnect --regcode <REGISTRATION_CODE>\n"
                f"copy {credentials_file} and {SUSECONNECT_CONFIG} from a registered system, or set\n"
                "  config_opts['suse_subscription_regcode'] = '<REGISTRATION_CODE>'\n"
                "You can get a free 60-day evaluation subscription at:\n"
                "  https://www.suse.com/download/sles/")
        regcodes = _request_regcodes(server, verify, credentials)
        if regcodes == []:
            raise exception.ConfigError(
                "The SUSE subscriptions of this system are all expired")

    product = _request_product(server, verify, product_query, regcodes, credentials)

    # Basic authentication is only needed with RMT and SMT, which return no regcodes.
    repo_credentials = credentials if regcodes is None else None
    opts["suse_subscription_repos"] = _product_repositories(opts, product, [], repo_credentials)

    if not _bootstrap_needs_own_repositories(opts):
        return

    bootstrap_arch = config.get_bootstrap_repo_arch(opts)
    bootstrap_extensions = opts["suse_subscription_bootstrap_extensions"]
    if bootstrap_arch != product_query["arch"]:
        product = _request_product(server, verify, dict(product_query, arch=bootstrap_arch),
                                   regcodes, credentials)

    # Mock copies every 'bootstrap_<option>' over '<option>' in the bootstrap
    # config, so the same dnf.conf template picks these up.
    opts["bootstrap_suse_subscription_repos"] = _product_repositories(
        opts, product, bootstrap_extensions, repo_credentials)
