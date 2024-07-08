config_opts['chroot_setup_cmd'] = 'install @buildsys-build'

config_opts['yum.conf'] += """
[epel]
name=Extra Packages for Enterprise Linux $releasever - $basearch
mirrorlist=http://mirrors.fedoraproject.org/mirrorlist?repo=epel-7&arch=$basearch
failovermethod=priority
gpgkey=file:///usr/share/distribution-gpg-keys/epel/RPM-GPG-KEY-EPEL-7
gpgcheck=1
skip_if_unavailable=False

[epel-testing]
name=Extra Packages for Enterprise Linux $releasever - Testing - $basearch
enabled=0
mirrorlist=http://mirrors.fedoraproject.org/mirrorlist?repo=testing-epel7&arch=$basearch
failovermethod=priority
skip_if_unavailable=False

[local]
name=local
baseurl=https://kojipkgs.fedoraproject.org/repos/epel7-build/latest/$basearch/
cost=2000
enabled=0
skip_if_unavailable=False

[epel-debuginfo]
name=Extra Packages for Enterprise Linux $releasever - $basearch - Debug
mirrorlist=http://mirrors.fedoraproject.org/mirrorlist?repo=epel-debug-7&arch=$basearch
failovermethod=priority
enabled=0
skip_if_unavailable=False
"""
