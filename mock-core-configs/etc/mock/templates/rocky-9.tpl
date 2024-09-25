config_opts['chroot_setup_cmd'] = 'install bash bzip2 coreutils cpio diffutils redhat-release findutils gawk glibc-minimal-langpack grep gzip info patch redhat-rpm-config rpm-build sed tar unzip util-linux which xz'
config_opts['dist'] = 'el9'  # only useful for --resultdir variable subst
config_opts['releasever'] = '9'
config_opts['package_manager'] = 'dnf'
config_opts['extra_chroot_dirs'] = [ '/run/lock', ]
config_opts['bootstrap_image'] = 'quay.io/rockylinux/rockylinux:9'


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
module_platform_id=platform:el9
user_agent={{ user_agent }}
tsflags=nodocs

[baseos]
name=Rocky Linux $releasever - BaseOS
mirrorlist=https://mirrors.rockylinux.org/mirrorlist?arch=$basearch&repo=BaseOS-$releasever
#baseurl=http://dl.rockylinux.org/pub/rocky/$releasever/BaseOS/$basearch/os/
gpgcheck=1
enabled=1
metadata_expire=6h
gpgkey=file:///usr/share/distribution-gpg-keys/rocky/RPM-GPG-KEY-Rocky-9

[appstream]
name=Rocky Linux $releasever - AppStream
mirrorlist=https://mirrors.rockylinux.org/mirrorlist?arch=$basearch&repo=AppStream-$releasever
#baseurl=http://dl.rockylinux.org/pub/rocky/$releasever/AppStream/$basearch/os/
gpgcheck=1
enabled=1
metadata_expire=6h
gpgkey=file:///usr/share/distribution-gpg-keys/rocky/RPM-GPG-KEY-Rocky-9

[crb]
name=Rocky Linux $releasever - CRB
mirrorlist=https://mirrors.rockylinux.org/mirrorlist?arch=$basearch&repo=CRB-$releasever
#baseurl=http://dl.rockylinux.org/pub/rocky/$releasever/CRB/$basearch/os/
gpgcheck=1
enabled=1
metadata_expire=6h
gpgkey=file:///usr/share/distribution-gpg-keys/rocky/RPM-GPG-KEY-Rocky-9

[extras]
name=Rocky Linux $releasever - Extras
mirrorlist=https://mirrors.rockylinux.org/mirrorlist?arch=$basearch&repo=extras-$releasever
#baseurl=http://dl.rockylinux.org/pub/rocky/$releasever/extras/$basearch/os/
gpgcheck=1
enabled=1
metadata_expire=6h
gpgkey=file:///usr/share/distribution-gpg-keys/rocky/RPM-GPG-KEY-Rocky-9

[devel]
name=Rocky Linux $releasever - Devel WARNING! FOR BUILDROOT ONLY DO NOT LEAVE ENABLED
mirrorlist=https://mirrors.rockylinux.org/mirrorlist?arch=$basearch&repo=devel-$releasever
#baseurl=http://dl.rockylinux.org/pub/rocky/$releasever/devel/$basearch/os/
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/rocky/RPM-GPG-KEY-Rocky-9

[highavailability]
name=Rocky Linux $releasever - High Availability
mirrorlist=https://mirrors.rockylinux.org/mirrorlist?arch=$basearch&repo=HighAvailability-$releasever
#baseurl=http://dl.rockylinux.org/$contentdir/$releasever/HighAvailability/$basearch/os/
gpgcheck=1
enabled=0
metadata_expire=6h
gpgkey=file:///usr/share/distribution-gpg-keys/rocky/RPM-GPG-KEY-Rocky-9

[resilientstorage]
name=Rocky Linux $releasever - Resilient Storage
mirrorlist=https://mirrors.rockylinux.org/mirrorlist?arch=$basearch&repo=ResilientStorage-$releasever
#baseurl=http://dl.rockylinux.org/$contentdir/$releasever/ResilientStorage/$basearch/os/
gpgcheck=1
enabled=0
metadata_expire=6h
gpgkey=file:///usr/share/distribution-gpg-keys/rocky/RPM-GPG-KEY-Rocky-9

[nfv]
name=Rocky Linux $releasever - NFV
mirrorlist=https://mirrors.rockylinux.org/mirrorlist?arch=$basearch&repo=NFV-$releasever
#baseurl=http://dl.rockylinux.org/$contentdir/$releasever/NFV/$basearch/os/
gpgcheck=1
enabled=0
metadata_expire=6h
gpgkey=file:///usr/share/distribution-gpg-keys/rocky/RPM-GPG-KEY-Rocky-9

[rt]
name=Rocky Linux $releasever - Realtime
mirrorlist=https://mirrors.rockylinux.org/mirrorlist?arch=$basearch&repo=RT-$releasever
#baseurl=http://dl.rockylinux.org/$contentdir/$releasever/RT/$basearch/os/
gpgcheck=1
enabled=0
metadata_expire=6h
gpgkey=file:///usr/share/distribution-gpg-keys/rocky/RPM-GPG-KEY-Rocky-9

[baseos-debug]
name=Rocky Linux $releasever - BaseOS - Debug
mirrorlist=https://mirrors.rockylinux.org/mirrorlist?arch=$basearch&repo=BaseOS-$releasever-debug
#baseurl=http://dl.rockylinux.org/pub/rocky/$releasever/BaseOS/$basearch/debug/tree/
gpgcheck=1
enabled=0
metadata_expire=6h
gpgkey=file:///usr/share/distribution-gpg-keys/rocky/RPM-GPG-KEY-Rocky-9

[baseos-source]
name=Rocky Linux $releasever - BaseOS - Source
mirrorlist=https://mirrors.rockylinux.org/mirrorlist?arch=source&repo=BaseOS-$releasever-source
#baseurl=http://dl.rockylinux.org/pub/rocky/$releasever/BaseOS/source/tree/
gpgcheck=1
enabled=0
metadata_expire=6h
gpgkey=file:///usr/share/distribution-gpg-keys/rocky/RPM-GPG-KEY-Rocky-9

[appstream-debug]
name=Rocky Linux $releasever - AppStream - Debug
mirrorlist=https://mirrors.rockylinux.org/mirrorlist?arch=$basearch&repo=AppStream-$releasever-debug
#baseurl=http://dl.rockylinux.org/pub/rocky/$releasever/AppStream/$basearch/debug/tree/
gpgcheck=1
enabled=0
metadata_expire=6h
gpgkey=file:///usr/share/distribution-gpg-keys/rocky/RPM-GPG-KEY-Rocky-9

[appstream-source]
name=Rocky Linux $releasever - AppStream - Source
mirrorlist=https://mirrors.rockylinux.org/mirrorlist?arch=source&repo=AppStream-$releasever-source
#baseurl=http://dl.rockylinux.org/pub/rocky/$releasever/AppStream/source/tree/
gpgcheck=1
enabled=0
metadata_expire=6h
gpgkey=file:///usr/share/distribution-gpg-keys/rocky/RPM-GPG-KEY-Rocky-9

[crb-debug]
name=Rocky Linux $releasever - CRB - Debug
mirrorlist=https://mirrors.rockylinux.org/mirrorlist?arch=$basearch&repo=CRB-$releasever-debug
#baseurl=http://dl.rockylinux.org/pub/rocky/$releasever/CRB/$basearch/debug/tree/
gpgcheck=1
enabled=0
metadata_expire=6h
gpgkey=file:///usr/share/distribution-gpg-keys/rocky/RPM-GPG-KEY-Rocky-9

[crb-source]
name=Rocky Linux $releasever - CRB - Source
mirrorlist=https://mirrors.rockylinux.org/mirrorlist?arch=source&repo=CRB-$releasever-source
#baseurl=http://dl.rockylinux.org/pub/rocky/$releasever/CRB/source/tree/
gpgcheck=1
enabled=0
metadata_expire=6h
gpgkey=file:///usr/share/distribution-gpg-keys/rocky/RPM-GPG-KEY-Rocky-9

[extras-debug]
name=Rocky Linux $releasever - Extras Debug
mirrorlist=https://mirrors.rockylinux.org/mirrorlist?arch=$basearch&repo=extras-$releasever-debug
#baseurl=http://dl.rockylinux.org/pub/rocky/$releasever/extras/$basearch/debug/tree/
gpgcheck=1
enabled=0
metadata_expire=6h
gpgkey=file:///usr/share/distribution-gpg-keys/rocky/RPM-GPG-KEY-Rocky-9

[extras-source]
name=Rocky Linux $releasever - Extras Source
mirrorlist=https://mirrors.rockylinux.org/mirrorlist?arch=$basearch&repo=extras-$releasever-source
#baseurl=http://dl.rockylinux.org/pub/rocky/$releasever/extras/source/tree/
gpgcheck=1
enabled=0
metadata_expire=6h
gpgkey=file:///usr/share/distribution-gpg-keys/rocky/RPM-GPG-KEY-Rocky-9

[highavailability-debug]
name=Rocky Linux $releasever - High Availability - Debug
mirrorlist=https://mirrors.rockylinux.org/mirrorlist?arch=$basearch&repo=HighAvailability-$releasever-debug$rltype
#baseurl=http://dl.rockylinux.org/$contentdir/$releasever/HighAvailability/$basearch/debug/tree/
gpgcheck=1
enabled=0
metadata_expire=6h
gpgkey=file:///usr/share/distribution-gpg-keys/rocky/RPM-GPG-KEY-Rocky-9

[highavailability-source]
name=Rocky Linux $releasever - High Availability - Source
mirrorlist=https://mirrors.rockylinux.org/mirrorlist?arch=source&repo=HighAvailability-$releasever-source$rltype
#baseurl=http://dl.rockylinux.org/$contentdir/$releasever/HighAvailability/source/tree/
gpgcheck=1
enabled=0
metadata_expire=6h
gpgkey=file:///usr/share/distribution-gpg-keys/rocky/RPM-GPG-KEY-Rocky-9

[resilientstorage-debug]
name=Rocky Linux $releasever - Resilient Storage - Debug
mirrorlist=https://mirrors.rockylinux.org/mirrorlist?arch=$basearch&repo=ResilientStorage-$releasever-debug$rltype
#baseurl=http://dl.rockylinux.org/$contentdir/$releasever/ResilientStorage/$basearch/debug/tree/
gpgcheck=1
enabled=0
metadata_expire=6h
gpgkey=file:///usr/share/distribution-gpg-keys/rocky/RPM-GPG-KEY-Rocky-9

[resilientstorage-source]
name=Rocky Linux $releasever - Resilient Storage - Source
mirrorlist=https://mirrors.rockylinux.org/mirrorlist?arch=source&repo=ResilientStorage-$releasever-source$rltype
#baseurl=http://dl.rockylinux.org/$contentdir/$releasever/ResilientStorage/source/tree/
gpgcheck=1
enabled=0
metadata_expire=6h
gpgkey=file:///usr/share/distribution-gpg-keys/rocky/RPM-GPG-KEY-Rocky-9

[nfv-debug]
name=Rocky Linux $releasever - NFV Debug
mirrorlist=https://mirrors.rockylinux.org/mirrorlist?arch=$basearch&repo=RT-$releasever-debug$rltype
#baseurl=http://dl.rockylinux.org/$contentdir/$releasever/NFV/$basearch/debug/tree/
gpgcheck=1
enabled=0
metadata_expire=6h
gpgkey=file:///usr/share/distribution-gpg-keys/rocky/RPM-GPG-KEY-Rocky-9

[nfv-source]
name=Rocky Linux $releasever - NFV Source
mirrorlist=https://mirrors.rockylinux.org/mirrorlist?arch=$basearch&repo=RT-$releasever-source$rltype
#baseurl=http://dl.rockylinux.org/$contentdir/$releasever/NFV/source/tree/
gpgcheck=1
enabled=0
metadata_expire=6h
gpgkey=file:///usr/share/distribution-gpg-keys/rocky/RPM-GPG-KEY-Rocky-9

[rt-debug]
name=Rocky Linux $releasever - Realtime Debug
mirrorlist=https://mirrors.rockylinux.org/mirrorlist?arch=$basearch&repo=RT-$releasever-debug$rltype
#baseurl=http://dl.rockylinux.org/$contentdir/$releasever/RT/$basearch/debug/tree/
gpgcheck=1
enabled=0
metadata_expire=6h
gpgkey=file:///usr/share/distribution-gpg-keys/rocky/RPM-GPG-KEY-Rocky-9

[rt-source]
name=Rocky Linux $releasever - Realtime Source
mirrorlist=https://mirrors.rockylinux.org/mirrorlist?arch=$basearch&repo=RT-$releasever-source$rltype
#baseurl=http://dl.rockylinux.org/$contentdir/$releasever/RT/source/tree/
gpgcheck=1
enabled=0
metadata_expire=6h
gpgkey=file:///usr/share/distribution-gpg-keys/rocky/RPM-GPG-KEY-Rocky-9


"""
