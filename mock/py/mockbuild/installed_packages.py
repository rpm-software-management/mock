"""
Helper methods for getting list of installed packages, and corresponding
packages' metadata
"""

import os
import subprocess
import mockbuild.exception


def _subprocess_executor(command):
    """
    We use doOutChroot normally in query_packages* methods, this is a helper
    for testing purposes.
    """
    return subprocess.check_output(command, env={"LC_ALL": "C"}).decode("utf-8")


def query_packages(fields, chrootpath=None, executor=_subprocess_executor):
    """
    Query the list of installed packages, including FIELDS metadata, from
    CHROOTPATH.

    The FIELDS argument is an array of RPM tags from 'rpm --querytags', without
    the '%{}' syntax, for example ['name'] queries for %{name}'.  There's an
    additional non-standard "signature" field parsed from the standard
    "%{sigpgp:pgpsig}" field (the last 8 hex characters).

    CHROOTPATH is the chroot directory with RPM DB.  If CHROOTPATH is not
    specified, the method uses the rpmdb from host.

    EXECUTOR is a callback accepting a single argument - command that will be
    executed, and its standard output returned as unicode multiline string.

    The method returns a list of dictionaries (package metadata info) in a
    format documented on
        https://docs.pagure.org/koji/content_generator_metadata/#buildroots
    For example:

    [{
       "license": "LicenseRef-Fedora-Public-Domain",
       "name": "filesystem",
       "version": "3.18",
       "release": "23.fc41",
       "arch": "x86_64",
       "epoch": null,
       "sigmd5": "dc6edb2b7e390e5f0994267d22b9dc1a",
       "signature": null
    }]
    """
    package_list_cmd = ["rpm", "-qa"]
    if chrootpath:
        package_list_cmd += ["--root", chrootpath]
    package_list_cmd.append("--qf")

    # HACK: Zero-termination is not possible with 'rpm -q --qf QUERYSTRIG', so
    # this is a hack.  But how likely we can expect the following string in the
    # real packages' metadata?
    separator = '|/@'

    def _query_key(key):
        # The Koji Content Generator's "signature" field can be queried via %{sigpgp}
        if key == "signature":
            return "sigpgp:pgpsig"
        return key

    query_fields = [_query_key(f) for f in fields]
    package_list_cmd.append(separator.join(f"%{{{x}}}" for x in query_fields) + "\n")

    def _fixup(package):
        """ polish the package's metadata output """
        key = "signature"
        if key in package:
            if package[key] == "(none)":
                package[key] = None
            else:
                # RSA/SHA256, Mon Jul 29 10:12:32 2024, Key ID 2322d3d94bf0c9db
                # Get just last 8 chars --->                           ^^^^^^^^
                package[key] = package[key].split()[-1][-8:]
        key = "epoch"
        if package[key] == "(none)":
            package[key] = None
        return package

    return [_fixup(p) for p in [dict(zip(fields, line.split(separator))) for
                                line in
                                sorted(executor(package_list_cmd).splitlines())]
            if p["name"] != "gpg-pubkey"]


def query_packages_location(packages, chrootpath=None,
                            executor=_subprocess_executor, dnf_cmd="/bin/dnf"):
    """
    Detect the URLs of the PACKAGES - array of dictionaries (see the output
    from query_packages()) in available RPM repositories (/etc/yum.repos.d).
    This method modifies PACKAGES in-situ, it adds "url" field to every single
    dictionary in the PACKAGES array.

    CHROOTPATH is the chroot directory with RPM DB, if not specified, rpmdb
    from host is used.

    EXECUTOR is a callback accepting a single argument - command that will be
    executed, and its standard output returned as unicode multiline string.

    Example output:

    [{
       "name": "filesystem",
       "version": "3.18",
       ...
       "url": "https://example.com/fedora-repos-rawhide-42-0.1.noarch.rpm",
       ...
    }]
    """

    # Note: we do not support YUM in 2024+
    query_locations_cmd = [dnf_cmd]
    if chrootpath:
        query_locations_cmd += [f"--installroot={chrootpath}"]
    # The -q is necessary because of and similar:
    # https://github.com/rpm-software-management/dnf5/issues/1361
    query_locations_cmd += ["repoquery", "-q", "--location"]
    query_locations_cmd += [
        f"{p['name']}-{p['version']}-{p['release']}.{p['arch']}"
        for p in packages
    ]
    location_map = {}
    for url in executor(query_locations_cmd).splitlines():
        basename = os.path.basename(url)
        # name-arch pair should be unique on the box for every installed package
        name, _, _ = basename.rsplit("-", 2)
        arch = basename.split(".")[-2]
        location_map[f"{name}.{arch}"] = url

    for package in packages:
        name_arch = f"{package['name']}.{package['arch']}"
        try:
            package["url"] = location_map[name_arch]
        except KeyError as exc:
            raise mockbuild.exception.Error(f"Can't get location for {name_arch}") from exc
