config_opts['chroot_setup_cmd'] = 'install tar gcc-c++ redhat-rpm-config redhat-release which xz sed make bzip2 gzip gcc coreutils unzip shadow-utils diffutils cpio bash gawk rpm-build info patch util-linux findutils grep'
config_opts['dist'] = 'el8'  # only useful for --resultdir variable subst
config_opts['releasever'] = '8'
config_opts['package_manager'] = 'dnf'
config_opts['extra_chroot_dirs'] = [ '/run/lock', ]
config_opts['bootstrap_image'] = 'quay.io/rockylinux/rockylinux:8'


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

# Primary
[baseos]
name=Rocky Linux $releasever - BaseOS
mirrorlist=https://mirrors.rockylinux.org/mirrorlist?arch=$basearch&repo=BaseOS-$releasever
gpgcheck=1
enabled=1
gpgkey=file:///usr/share/distribution-gpg-keys/rocky/RPM-GPG-KEY-rockyofficial

[appstream]
name=Rocky Linux $releasever - AppStream
mirrorlist=https://mirrors.rockylinux.org/mirrorlist?arch=$basearch&repo=AppStream-$releasever
gpgcheck=1
enabled=1
gpgkey=file:///usr/share/distribution-gpg-keys/rocky/RPM-GPG-KEY-rockyofficial

[powertools]
name=Rocky Linux $releasever - PowerTools
mirrorlist=https://mirrors.rockylinux.org/mirrorlist?arch=$basearch&repo=PowerTools-$releasever
gpgcheck=1
enabled=1
gpgkey=file:///usr/share/distribution-gpg-keys/rocky/RPM-GPG-KEY-rockyofficial

[extras]
name=Rocky Linux $releasever - Extras
mirrorlist=https://mirrors.rockylinux.org/mirrorlist?arch=$basearch&repo=extras-$releasever
gpgcheck=1
enabled=1
gpgkey=file:///usr/share/distribution-gpg-keys/rocky/RPM-GPG-KEY-rockyofficial

[ha]
name=Rocky Linux $releasever - HighAvailability
mirrorlist=https://mirrors.rockylinux.org/mirrorlist?arch=$basearch&repo=HighAvailability-$releasever
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/rocky/RPM-GPG-KEY-rockyofficial

[resilient-storage]
name=Rocky Linux $releasever - ResilientStorage
mirrorlist=https://mirrors.rockylinux.org/mirrorlist?arch=$basearch&repo=ResilientStorage-$releasever
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/rocky/RPM-GPG-KEY-rockyofficial

[plus]
name=Rocky Linux $releasever - Plus
mirrorlist=https://mirrors.rockylinux.org/mirrorlist?arch=$basearch&repo=rockyplus-$releasever
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/rocky/RPM-GPG-KEY-rockyofficial

[devel]
name=Rocky Linux $releasever - Devel WARNING! FOR BUILDROOT AND KOJI USE
mirrorlist=https://mirrors.rockylinux.org/mirrorlist?arch=$basearch&repo=Devel-$releasever
gpgcheck=1
enabled=1
gpgkey=file:///usr/share/distribution-gpg-keys/rocky/RPM-GPG-KEY-rockyofficial

# Debuginfo
[baseos-debug]
name=Rocky Linux $releasever - BaseOS - Source
mirrorlist=https://mirrors.rockylinux.org/mirrorlist?arch=$basearch&repo=BaseOS-$releasever-debug
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/rocky/RPM-GPG-KEY-rockyofficial

[appstream-debug]
name=Rocky Linux $releasever - AppStream - Source
mirrorlist=https://mirrors.rockylinux.org/mirrorlist?arch=$basearch&repo=AppStream-$releasever-debug
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/rocky/RPM-GPG-KEY-rockyofficial

[ha-debug]
name=Rocky Linux $releasever - High Availability - Source
mirrorlist=https://mirrors.rockylinux.org/mirrorlist?arch=$basearch&repo=HighAvailability-$releasever-debug
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/rocky/RPM-GPG-KEY-rockyofficial

[powertools-debug]
name=Rocky Linux $releasever - PowerTools - Source
mirrorlist=https://mirrors.rockylinux.org/mirrorlist?arch=$basearch&repo=PowerTools-$releasever-debug
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/rocky/RPM-GPG-KEY-rockyofficial

[resilient-storage-debug]
name=Rocky Linux $releasever - Resilient Storage - Source
mirrorlist=https://mirrors.rockylinux.org/mirrorlist?arch=$basearch&repo=ResilientStorage-$releasever-debug
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/rocky/RPM-GPG-KEY-rockyofficial

# Source Repos
[baseos-source]
name=Rocky Linux $releasever - BaseOS - Source
mirrorlist=https://mirrors.rockylinux.org/mirrorlist?arch=source&repo=BaseOS-$releasever-source
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/rocky/RPM-GPG-KEY-rockyofficial

[appstream-source]
name=Rocky Linux $releasever - AppStream - Source
mirrorlist=https://mirrors.rockylinux.org/mirrorlist?arch=source&repo=AppStream-$releasever-source
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/rocky/RPM-GPG-KEY-rockyofficial

[ha-source]
name=Rocky Linux $releasever - High Availability - Source
mirrorlist=https://mirrors.rockylinux.org/mirrorlist?arch=source&repo=HighAvailability-$releasever-source
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/rocky/RPM-GPG-KEY-rockyofficial

[powertools-source]
name=Rocky Linux $releasever - PowerTools - Source
mirrorlist=https://mirrors.rockylinux.org/mirrorlist?arch=source&repo=PowerTools-$releasever-source
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/rocky/RPM-GPG-KEY-rockyofficial

[resilient-storage-source]
name=Rocky Linux $releasever - Resilient Storage - Source
mirrorlist=https://mirrors.rockylinux.org/mirrorlist?arch=source&repo=ResilientStorage-$releasever-source
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/rocky/RPM-GPG-KEY-rockyofficial

"""
