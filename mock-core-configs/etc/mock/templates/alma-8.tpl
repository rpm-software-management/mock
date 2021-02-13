config_opts['chroot_setup_cmd'] = 'install tar gcc-c++ redhat-rpm-config redhat-release which xz sed make bzip2 gzip gcc coreutils unzip shadow-utils diffutils cpio bash gawk rpm-build info patch util-linux findutils grep'
config_opts['dist'] = 'el8'  # only useful for --resultdir variable subst
config_opts['releasever'] = '8'
config_opts['package_manager'] = 'dnf'
config_opts['extra_chroot_dirs'] = [ '/run/lock', ]
config_opts['bootstrap_image'] = 'alma:8'


config_opts['dnf.conf'] = """
[main]
keepcache=1
debuglevel=2
reposdir=/dev/null
logfile=/var/log/yum.log
retries=20
obsoletes=1
gpgcheck=0
assumeyes=1
syslog_ident=mock
syslog_device=
metadata_expire=0
mdpolicy=group:primary
best=1
protected_packages=
module_platform_id=platform:el8
user_agent={{ user_agent }}

# almalinux.repo
#
# The mirror system uses the connecting IP address of the client and the
# update status of each mirror to pick mirrors that are updated to and
# geographically close to the client.  You should use this for AlmaLinux updates
# unless you are manually picking other mirrors.
#
[baseos]
name=AlmaLinux 8.3 - BaseOS
baseurl=https://repo.almalinux.org/almalinux/8/BaseOS/$basearch/os/
enabled=1
gpgcheck=0
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-AlmaLinux

[appstream]
name=AlmaLinux 8.3 - AppStream
baseurl=https://repo.almalinux.org/almalinux/8/AppStream/$basearch/os/
enabled=1
gpgcheck=0
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-AlmaLinux

[powertools]
name=AlmaLinux 8.3 - PowerTools
baseurl=https://repo.almalinux.org/almalinux/8/PowerTools/$basearch/os/
enabled=1
gpgcheck=0
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-AlmaLinux

[extras]
name=AlmaLinux 8.3 - Extras
baseurl=https://repo.almalinux.org/almalinux/8/extras/$basearch/os/
enabled=1
gpgcheck=0
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-AlmaLinux

## Sources
[baseos-source]
name=AlmaLinux 8.3 - BaseOS Source
baseurl=https://repo.almalinux.org/almalinux/8/BaseOS/Source/
enabled=0
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-AlmaLinux

[appstream-source]
name=AlmaLinux 8.3 - AppStream Source
baseurl=https://repo.almalinux.org/almalinux/8/AppStream/Source/
enabled=0
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-AlmaLinux

[powertools-source]
name=AlmaLinux 8.3 - PowerTools Source
baseurl=https://repo.almalinux.org/almalinux/8/PowerTools/Source/
enabled=0
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-AlmaLinux

[extras-source]
name=AlmaLinux 8.3 - Extras Source
baseurl=https://repo.almalinux.org/almalinux/8/extras/Source/
enabled=0
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-AlmaLinux
## Debuginfo
[baseos-debuginfo]
name=AlmaLinux 8.3 - BaseOS debuginfo
baseurl=https://repo.almalinux.org/almalinux/8/BaseOS/debug/$basearch/
enabled=0
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-AlmaLinux

[appstream-debuginfo]
name=AlmaLinux 8.3 - AppStream debuginfo
baseurl=https://repo.almalinux.org/almalinux/8/AppStream/debug/$basearch/
enabled=0
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-AlmaLinux

[powertools-debuginfo]
name=AlmaLinux 8.3 - PowerTools debuginfo
baseurl=https://repo.almalinux.org/almalinux/8/PowerTools/debug/$basearch/
enabled=0
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-AlmaLinux

[extras-debuginfo]
name=AlmaLinux 8.3 - Extras debuginfo
baseurl=https://repo.almalinux.org/almalinux/8/extras/debug/$basearch/
enabled=0
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-AlmaLinux
"""
