config_opts['chroot_setup_cmd'] += " epel-rpm-macros"

config_opts['dnf.conf'] += """

# The baseurls below differ from the ones used in
# epel-release-almalinux-altarch, which rely on a dnf variable expansion
# feature that is only available since dnf 4.18.0.  In some configurations mock
# will be using the host dnf to bootstrap the chroot, which could be older and
# lack those features, leading to problems.  The alternative is to use this
# simplified baseurl here in this template for AlmaLinux, and a different
# baseurl in another template for AlmaLinux Kitten.

[epel]
name=Extra Packages for Enterprise Linux $releasever from AlmaLinux - x86_64_v2
# mirrorlist=https://epel.mirrors.almalinux.org/mirrorlist/{{ releasever_major }}/epel?arch=x86_64_v2
baseurl=https://epel.repo.almalinux.org/{{ releasever_major }}/x86_64_v2/
gpgkey=file:///usr/share/distribution-gpg-keys/alma/RPM-GPG-KEY-AlmaLinux-$releasever-EPEL-AltArch
gpgcheck=1
countme=1
enabled=1

[epel-debuginfo]
name=Extra Packages for Enterprise Linux $releasever from AlmaLinux - x86_64_v2 - Debug
# mirrorlist=https://epel.mirrors.almalinux.org/mirrorlist/{{ releasever_major }}z/epel-debuginfo?arch=x86_64_v2
baseurl=https://epel.vault.almalinux.org/{{ releasever_major }}/debug/x86_64_v2/
gpgkey=file:///usr/share/distribution-gpg-keys/alma/RPM-GPG-KEY-AlmaLinux-$releasever-EPEL-AltArch
gpgcheck=1
enabled=0

[epel-source]
name=Extra Packages for Enterprise Linux $releasever from AlmaLinux - x86_64_v2 - Source
# mirrorlist=https://epel.mirrors.almalinux.org/mirrorlist/{{ releasever_major }}z/epel-source?arch=x86_64_v2
baseurl=https://epel.vault.almalinux.org/{{ releasever_major }}/Source/
gpgkey=file:///usr/share/distribution-gpg-keys/alma/RPM-GPG-KEY-AlmaLinux-$releasever-EPEL-AltArch
gpgcheck=1
enabled=0
"""
