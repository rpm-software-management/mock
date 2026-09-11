config_opts['chroot_setup_cmd'] += " epel-rpm-macros"

config_opts['dnf.conf'] += """

[epel]
name=Extra Packages for Enterprise Linux $releasever from AlmaLinux - x86_64_v2
# mirrorlist=https://epel.mirrors.almalinux.org/mirrorlist/{{ releasever_major }}s/epel?arch=x86_64_v2
baseurl=https://epel.repo.almalinux.org/{{ releasever_major }}s/x86_64_v2/
gpgkey=file:///usr/share/distribution-gpg-keys/alma/RPM-GPG-KEY-AlmaLinux-$releasever-EPEL-AltArch
gpgcheck=1
countme=1
"""
