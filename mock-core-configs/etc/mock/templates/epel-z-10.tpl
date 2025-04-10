config_opts['chroot_setup_cmd'] += " epel-rpm-macros"

config_opts['dnf.conf'] += """

# The metalinks below differ from the ones used in epel-release.  The
# epel-release metalinks rely on a dnf variable expansion feature that is only
# available since dnf 4.18.0.  In some configurations mock will be using the
# host dnf to bootstrap the chroot, which could be older and lack those
# features, leading to problems.  The alternative is to use this simplified
# metalink here in this template for RHEL, and a different metalink in
# another template for CentOS Stream.

[epel]
name=Extra Packages for Enterprise Linux $releasever - $basearch
metalink=https://mirrors.fedoraproject.org/metalink?repo=epel-z-{{ releasever_major }}&arch=$basearch
gpgkey=file:///usr/share/distribution-gpg-keys/epel/RPM-GPG-KEY-EPEL-{{ releasever_major }}
gpgcheck=1
countme=1

[epel-testing]
name=Extra Packages for Enterprise Linux $releasever - Testing - $basearch
metalink=https://mirrors.fedoraproject.org/metalink?repo=epel-z-testing-{{ releasever_major }}&arch=$basearch
gpgkey=file:///usr/share/distribution-gpg-keys/epel/RPM-GPG-KEY-EPEL-{{ releasever_major }}
gpgcheck=1
countme=1
enabled=0

{% if koji_primary_repo == "epel" %}

# The baseurl below is a symlink in the koji infrastructure that moves forward
# over time to the buildroot repo of the minor version tag matching RHEL.

[local]
name=Extra Packages for Enterprise Linux $releasever - Koji Local - BUILDROOT ONLY!
baseurl=https://kojipkgs.fedoraproject.org/repos/epel{{ releasever_major }}z/latest/$basearch/
cost=2000
enabled=0
skip_if_unavailable=False
{% endif %}
"""
