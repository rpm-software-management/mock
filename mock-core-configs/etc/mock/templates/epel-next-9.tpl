config_opts['dnf.conf'] += """

[epel-next]
name=Extra Packages for Enterprise Linux $releasever - Next - $basearch
metalink=https://mirrors.fedoraproject.org/metalink?repo=epel-next-$releasever&arch=$basearch
enabled=1
gpgcheck=1
gpgkey=file:///usr/share/distribution-gpg-keys/epel/RPM-GPG-KEY-EPEL-$releasever
skip_if_unavailable=False

[epel-next-debuginfo]
name=Extra Packages for Enterprise Linux $releasever - Next - $basearch - Debug
metalink=https://mirrors.fedoraproject.org/metalink?repo=epel-next-debug-$releasever&arch=$basearch
enabled=0
gpgcheck=1
gpgkey=file:///usr/share/distribution-gpg-keys/epel/RPM-GPG-KEY-EPEL-$releasever
skip_if_unavailable=False

[epel-next-source]
name=Extra Packages for Enterprise Linux $releasever - Next - $basearch - Source
metalink=https://mirrors.fedoraproject.org/metalink?repo=epel-next-source-$releasever&arch=$basearch
enabled=0
gpgcheck=1
gpgkey=file:///usr/share/distribution-gpg-keys/epel/RPM-GPG-KEY-EPEL-$releasever
skip_if_unavailable=False

[epel-next-testing]
name=Extra Packages for Enterprise Linux $releasever - Next - Testing - $basearch
metalink=https://mirrors.fedoraproject.org/metalink?repo=epel-testing-next-$releasever&arch=$basearch
enabled=0
gpgcheck=1
gpgkey=file:///usr/share/distribution-gpg-keys/epel/RPM-GPG-KEY-EPEL-$releasever
skip_if_unavailable=False

[epel-next-testing-debuginfo]
name=Extra Packages for Enterprise Linux $releasever - Next - Testing - $basearch - Debug
metalink=https://mirrors.fedoraproject.org/metalink?repo=epel-testing-next-debug-$releasever&arch=$basearch
enabled=0
gpgcheck=1
gpgkey=file:///usr/share/distribution-gpg-keys/epel/RPM-GPG-KEY-EPEL-$releasever
skip_if_unavailable=False

[epel-next-testing-source]
name=Extra Packages for Enterprise Linux $releasever - Next - Testing - $basearch - Source
metalink=https://mirrors.fedoraproject.org/metalink?repo=epel-testing-next-source-$releasever&arch=$basearch
enabled=0
gpgcheck=1
gpgkey=file:///usr/share/distribution-gpg-keys/epel/RPM-GPG-KEY-EPEL-$releasever
skip_if_unavailable=False

{% if koji_primary_repo != None and koji_primary_repo != "epel-next" %}
[local-epel-next]
{% else %}
[local]
{% endif %}
name=Extra Packages for Enterprise Linux $releasever - Next - Koji Local - BUILDROOT ONLY!
baseurl=https://kojipkgs.fedoraproject.org/repos/epel$releasever-next-build/latest/$basearch/
cost=2000
enabled=0
skip_if_unavailable=False
"""
