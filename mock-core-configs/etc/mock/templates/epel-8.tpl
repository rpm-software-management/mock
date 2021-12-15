config_opts['chroot_setup_cmd'] += " epel-rpm-macros"

config_opts['dnf.conf'] += """

[epel]
name=Extra Packages for Enterprise Linux $releasever - $basearch
mirrorlist=http://mirrors.fedoraproject.org/mirrorlist?repo=epel-8&arch=$basearch
failovermethod=priority
gpgkey=file:///usr/share/distribution-gpg-keys/epel/RPM-GPG-KEY-EPEL-8
gpgcheck=1
skip_if_unavailable=False

[epel-testing]
name=Extra Packages for Enterprise Linux $releasever - Testing - $basearch
enabled=0
mirrorlist=http://mirrors.fedoraproject.org/mirrorlist?repo=testing-epel8&arch=$basearch
failovermethod=priority
skip_if_unavailable=False

[epel-debuginfo]
name=Extra Packages for Enterprise Linux $releasever - $basearch - Debug
mirrorlist=http://mirrors.fedoraproject.org/mirrorlist?repo=epel-debug-8&arch=$basearch
failovermethod=priority
enabled=0
skip_if_unavailable=False

[epel-source]
name=Extra Packages for Enterprise Linux $releasever - $basearch - Source
mirrorlist=http://mirrors.fedoraproject.org/mirrorlist?repo=epel-source-8&arch=$basearch
failovermethod=priority
enabled=0
skip_if_unavailable=False

[epel-modular]
name=Extra Packages for Enterprise Linux Modular $releasever - $basearch
mirrorlist=http://mirrors.fedoraproject.org/mirrorlist?repo=epel-modular-8&arch=$basearch
failovermethod=priority
enabled=0
skip_if_unavailable=False

[epel-modular-debuginfo]
name=Extra Packages for Enterprise Linux Modular $releasever - $basearch - Debug
mirrorlist=http://mirrors.fedoraproject.org/mirrorlist?repo=epel-modular-debug-8&arch=$basearch
failovermethod=priority
enabled=0
skip_if_unavailable=False

[epel-modular-source]
name=Extra Packages for Enterprise Linux Modular $releasever - $basearch - Source
mirrorlist=http://mirrors.fedoraproject.org/mirrorlist?repo=epel-modular-source-8&arch=$basearch
failovermethod=priority
enabled=0
skip_if_unavailable=False

{% if koji_primary_repo != None and koji_primary_repo != "epel" %}
[local-epel]
{% else %}
[local]
{% endif %}
name=Extra Packages for Enterprise Linux $releasever - Koji Local - BUILDROOT ONLY!
baseurl=https://kojipkgs.fedoraproject.org/repos/epel$releasever-build/latest/$basearch/
cost=2000
enabled=0
skip_if_unavailable=False
"""
