config_opts['chroot_setup_cmd'] = 'install bash bzip2 coreutils cpio diffutils redhat-release findutils gawk glibc-minimal-langpack grep gzip info patch redhat-rpm-config rpm-build sed tar unzip util-linux which xz'
config_opts['dist'] = 'el10.alma'  # only useful for --resultdir variable subst
config_opts['releasever'] = '10'
config_opts['releasever_major'] = '10'
config_opts['package_manager'] = 'dnf'
config_opts['extra_chroot_dirs'] = [ '/run/lock', ]
config_opts['bootstrap_image'] = 'quay.io/almalinuxorg/almalinux:10-kitten'


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
install_weak_deps=0
protected_packages=
module_platform_id=platform:el10
user_agent={{ user_agent }}


[baseos]
name=AlmaLinux Kitten $releasever - BaseOS
mirrorlist=https://kitten.mirrors.almalinux.org/mirrorlist/$releasever-kitten/baseos
# baseurl=https://kitten.repo.almalinux.org/$releasever-kitten/BaseOS/$basearch/os/
enabled=1
gpgcheck=1
gpgkey=file:///usr/share/distribution-gpg-keys/alma/RPM-GPG-KEY-AlmaLinux-10
skip_if_unavailable=False

[appstream]
name=AlmaLinux Kitten $releasever - AppStream
mirrorlist=https://kitten.mirrors.almalinux.org/mirrorlist/$releasever-kitten/appstream
# baseurl=https://kitten.repo.almalinux.org/$releasever-kitten/AppStream/$basearch/os/
enabled=1
gpgcheck=1
gpgkey=file:///usr/share/distribution-gpg-keys/alma/RPM-GPG-KEY-AlmaLinux-10

[crb]
name=AlmaLinux Kitten $releasever - CRB
mirrorlist=https://kitten.mirrors.almalinux.org/mirrorlist/$releasever-kitten/crb
# baseurl=https://kitten.repo.almalinux.org/$releasever-kitten/CRB/$basearch/os/
enabled=1
gpgcheck=1
gpgkey=file:///usr/share/distribution-gpg-keys/alma/RPM-GPG-KEY-AlmaLinux-10

[extras-common]
name=AlmaLinux Kitten $releasever - Extras
mirrorlist=https://kitten.mirrors.almalinux.org/mirrorlist/$releasever-kitten/extras-common
# baseurl=https://kitten.repo.almalinux.org/$releasever-kitten/extras-common/$basearch/os/
enabled=1
gpgcheck=1
gpgkey=file:///usr/share/distribution-gpg-keys/alma/RPM-GPG-KEY-AlmaLinux-10

[devel]
name=AlmaLinux Kitten $releasever - Devel (WARNING: UNSUPPORTED - FOR BUILDROOT USE ONLY!)
mirrorlist=https://kitten.mirrors.almalinux.org/mirrorlist/$releasever-kitten/devel
# baseurl=https://kitten.repo.almalinux.org/$releasever-kitten/devel/$basearch/os/
enabled=0
gpgcheck=1
gpgkey=file:///usr/share/distribution-gpg-keys/alma/RPM-GPG-KEY-AlmaLinux-10

[baseos-debuginfo]
name=AlmaLinux Kitten $releasever - BaseOS debuginfo
mirrorlist=https://kitten.mirrors.almalinux.org/mirrorlist/$releasever-kitten/baseos-debuginfo
# baseurl=https://kitten.repo.almalinux.org/$releasever-kitten/BaseOS/debug/$basearch/
enabled=0
gpgcheck=1
gpgkey=file:///usr/share/distribution-gpg-keys/alma/RPM-GPG-KEY-AlmaLinux-10

[appstream-debuginfo]
name=AlmaLinux Kitten $releasever - AppStream debuginfo
mirrorlist=https://kitten.mirrors.almalinux.org/mirrorlist/$releasever-kitten/appstream-debuginfo
# baseurl=https://kitten.repo.almalinux.org/$releasever-kitten/AppStream/debug/$basearch/
enabled=0
gpgcheck=1
gpgkey=file:///usr/share/distribution-gpg-keys/alma/RPM-GPG-KEY-AlmaLinux-10

[crb-debuginfo]
name=AlmaLinux Kitten $releasever - CRB debuginfo
mirrorlist=https://kitten.mirrors.almalinux.org/mirrorlist/$releasever-kitten/crb-debuginfo
# baseurl=https://kitten.repo.almalinux.org/$releasever-kitten/CRB/debug/$basearch/
enabled=0
gpgcheck=1
gpgkey=file:///usr/share/distribution-gpg-keys/alma/RPM-GPG-KEY-AlmaLinux-10

[extras-common-debuginfo]
name=AlmaLinux Kitten $releasever - Extras debuginfo
mirrorlist=https://kitten.mirrors.almalinux.org/mirrorlist/$releasever-kitten/extras-common-debuginfo
# baseurl=https://kitten.repo.almalinux.org/$releasever-kitten/extras-common/debug/$basearch/
enabled=0
gpgcheck=1
gpgkey=file:///usr/share/distribution-gpg-keys/alma/RPM-GPG-KEY-AlmaLinux-10

[devel-debuginfo]
name=AlmaLinux Kitten $releasever - Devel debuginfo
mirrorlist=https://kitten.mirrors.almalinux.org/mirrorlist/$releasever-kitten/devel-debuginfo
# baseurl=https://kitten.repo.almalinux.org/$releasever-kitten/devel/debug/$basearch/
enabled=0
gpgcheck=1
gpgkey=file:///usr/share/distribution-gpg-keys/alma/RPM-GPG-KEY-AlmaLinux-10

[baseos-source]
name=AlmaLinux Kitten $releasever - BaseOS Source
mirrorlist=https://kitten.mirrors.almalinux.org/mirrorlist/$releasever-kitten/baseos-source
# baseurl=https://kitten.repo.almalinux.org/$releasever-kitten/BaseOS/Source/
enabled=0
gpgcheck=1
gpgkey=file:///usr/share/distribution-gpg-keys/alma/RPM-GPG-KEY-AlmaLinux-10

[appstream-source]
name=AlmaLinux Kitten $releasever - AppStream Source
mirrorlist=https://kitten.mirrors.almalinux.org/mirrorlist/$releasever-kitten/appstream-source
# baseurl=https://kitten.repo.almalinux.org/$releasever-kitten/AppStream/Source/
enabled=0
gpgcheck=1
gpgkey=file:///usr/share/distribution-gpg-keys/alma/RPM-GPG-KEY-AlmaLinux-10

[crb-source]
name=AlmaLinux Kitten $releasever - CRB Source
mirrorlist=https://kitten.mirrors.almalinux.org/mirrorlist/$releasever-kitten/crb-source
# baseurl=https://kitten.repo.almalinux.org/$releasever-kitten/CRB/Source/
enabled=0
gpgcheck=1
gpgkey=file:///usr/share/distribution-gpg-keys/alma/RPM-GPG-KEY-AlmaLinux-10

[extras-common-source]
name=AlmaLinux Kitten $releasever - Extras Source
mirrorlist=https://kitten.mirrors.almalinux.org/mirrorlist/$releasever-kitten/extras-common-source
# baseurl=https://kitten.repo.almalinux.org/$releasever-kitten/extras-common/Source/
enabled=0
gpgcheck=1
gpgkey=file:///usr/share/distribution-gpg-keys/alma/RPM-GPG-KEY-AlmaLinux-10

[devel-source]
name=AlmaLinux Kitten $releasever - Devel Source
mirrorlist=https://kitten.mirrors.almalinux.org/mirrorlist/$releasever-kitten/devel-source
# baseurl=https://kitten.repo.almalinux.org/$releasever-kitten/devel/Source/
enabled=0
gpgcheck=1
gpgkey=file:///usr/share/distribution-gpg-keys/alma/RPM-GPG-KEY-AlmaLinux-10

"""
