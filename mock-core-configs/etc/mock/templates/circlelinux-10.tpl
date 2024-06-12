config_opts['chroot_setup_cmd'] = 'install bash bzip2 coreutils cpio diffutils redhat-release findutils gawk glibc-minimal-langpack grep gzip info patch redhat-rpm-config rpm-build sed tar unzip util-linux which xz'
config_opts['dist'] = 'el10'  # only useful for --resultdir variable subst
config_opts['releasever'] = '10'
config_opts['package_manager'] = 'dnf'
config_opts['extra_chroot_dirs'] = [ '/run/lock', ]
config_opts['bootstrap_image'] = 'quay.io/cclinux/circlelinux:10'


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
name=Circle Linux $releasever - BaseOS
mirrorlist=https://mirrorlist.cclinux.org/mirrorlist?arch=$basearch&repo=BaseOS-$releasever
#baseurl=http://mirror.cclinux.org/$contentdir/$releasever/BaseOS/$basearch/os/
gpgcheck=1
enabled=1
gpgkey=file:///usr/share/distribution-gpg-keys/circle/RPM-GPG-KEY-circleofficial

[appstream]
name=Circle Linux $releasever - AppStream
mirrorlist=https://mirrorlist.cclinux.org/mirrorlist?arch=$basearch&repo=AppStream-$releasever
#baseurl=http://mirror.cclinux.org/$contentdir/$releasever/AppStream/$basearch/os/
gpgcheck=1
enabled=1
gpgkey=file:///usr/share/distribution-gpg-keys/circle/RPM-GPG-KEY-circleofficial

[crb]
name=Circle Linux $releasever - CRB
mirrorlist=https://mirrorlist.cclinux.org/mirrorlist?arch=$basearch&repo=CRB-$releasever
#baseurl=http://mirror.cclinux.org/$contentdir/$releasever/CRB/$basearch/os/
gpgcheck=1
enabled=1
gpgkey=file:///usr/share/distribution-gpg-keys/circle/RPM-GPG-KEY-circleofficial

[extras]
name=Circle Linux $releasever - Extras
mirrorlist=https://mirrorlist.cclinux.org/mirrorlist?arch=$basearch&repo=extras-$releasever
#baseurl=http://mirror.cclinux.org/$contentdir/$releasever/extras/$basearch/os/
gpgcheck=1
enabled=1
gpgkey=file:///usr/share/distribution-gpg-keys/circle/RPM-GPG-KEY-circleofficial

[devel]
name=Circle Linux $releasever - Devel WARNING! FOR BUILDROOT USE ONLY!
mirrorlist=https://mirrorlist.cclinux.org/mirrorlist?arch=$basearch&repo=devel-$releasever
#baseurl=http://mirror.cclinux.org/$contentdir/$releasever/devel/$basearch/os/
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/circle/RPM-GPG-KEY-circleofficial

[highavailability]
name=Circle Linux $releasever - High Availability
mirrorlist=https://mirrorlist.cclinux.org/mirrorlist?arch=$basearch&repo=HighAvailability-$releasever
#baseurl=http://mirror.cclinux.org/$contentdir/$releasever/HighAvailability/$basearch/os/
gpgcheck=1
enabled=0
metadata_expire=6h
gpgkey=file:///usr/share/distribution-gpg-keys/circle/RPM-GPG-KEY-circleofficial

[resilientstorage]
name=Circle Linux $releasever - Resilient Storage
mirrorlist=https://mirrorlist.cclinux.org/mirrorlist?arch=$basearch&repo=ResilientStorage-$releasever
#baseurl=http://mirror.cclinux.org/$contentdir/$releasever/ResilientStorage/$basearch/os/
gpgcheck=1
enabled=0
metadata_expire=6h
gpgkey=file:///usr/share/distribution-gpg-keys/circle/RPM-GPG-KEY-circleofficial

[nfv]
name=Circle Linux $releasever - NFV
mirrorlist=https://mirrorlist.cclinux.org/mirrorlist?arch=$basearch&repo=NFV-$releasever
#baseurl=http://mirror.cclinux.org/$contentdir/$releasever/NFV/$basearch/os/
gpgcheck=1
enabled=0
metadata_expire=6h
gpgkey=file:///usr/share/distribution-gpg-keys/circle/RPM-GPG-KEY-circleofficial

[rt]
name=Circle Linux $releasever - Realtime
mirrorlist=https://mirrorlist.cclinux.org/mirrorlist?arch=$basearch&repo=RT-$releasever
#baseurl=http://mirror.cclinux.org/$contentdir/$releasever/RT/$basearch/os/
gpgcheck=1
enabled=0
metadata_expire=6h
gpgkey=file:///usr/share/distribution-gpg-keys/circle/RPM-GPG-KEY-circleofficial

[baseos-debug]
name=Circle Linux $releasever - BaseOS - Debug
mirrorlist=https://mirrorlist.cclinux.org/mirrorlist?arch=$basearch&repo=BaseOS-$releasever-debug
#baseurl=http://mirror.cclinux.org/$contentdir/$releasever/BaseOS/$basearch/debug/tree/
gpgcheck=1
enabled=0
metadata_expire=6h
gpgkey=file:///usr/share/distribution-gpg-keys/circle/RPM-GPG-KEY-circleofficial

[baseos-source]
name=Circle Linux $releasever - BaseOS - Source
mirrorlist=https://mirrorlist.cclinux.org/mirrorlist?arch=source&repo=BaseOS-$releasever-source
#baseurl=http://mirror.cclinux.org/$contentdir/$releasever/BaseOS/source/tree/
gpgcheck=1
enabled=0
metadata_expire=6h
gpgkey=file:///usr/share/distribution-gpg-keys/circle/RPM-GPG-KEY-circleofficial

[appstream-debug]
name=Circle Linux $releasever - AppStream - Debug
mirrorlist=https://mirrorlist.cclinux.org/mirrorlist?arch=$basearch&repo=AppStream-$releasever-debug
#baseurl=http://mirror.cclinux.org/$contentdir/$releasever/AppStream/$basearch/debug/tree/
gpgcheck=1
enabled=0
metadata_expire=6h
gpgkey=file:///usr/share/distribution-gpg-keys/circle/RPM-GPG-KEY-circleofficial

[appstream-source]
name=Circle Linux $releasever - AppStream - Source
mirrorlist=https://mirrorlist.cclinux.org/mirrorlist?arch=source&repo=AppStream-$releasever-source
#baseurl=http://mirror.cclinux.org/$contentdir/$releasever/AppStream/source/tree/
gpgcheck=1
enabled=0
metadata_expire=6h
gpgkey=file:///usr/share/distribution-gpg-keys/circle/RPM-GPG-KEY-circleofficial

[crb-debug]
name=Circle Linux $releasever - CRB - Debug
mirrorlist=https://mirrorlist.cclinux.org/mirrorlist?arch=$basearch&repo=CRB-$releasever-debug
#baseurl=http://mirror.cclinux.org/$contentdir/$releasever/CRB/$basearch/debug/tree/
gpgcheck=1
enabled=0
metadata_expire=6h
gpgkey=file:///usr/share/distribution-gpg-keys/circle/RPM-GPG-KEY-circleofficial

[crb-source]
name=Circle Linux $releasever - CRB - Source
mirrorlist=https://mirrorlist.cclinux.org/mirrorlist?arch=source&repo=CRB-$releasever-source
#baseurl=http://mirror.cclinux.org/$contentdir/$releasever/CRB/source/tree/
gpgcheck=1
enabled=0
metadata_expire=6h
gpgkey=file:///usr/share/distribution-gpg-keys/circle/RPM-GPG-KEY-circleofficial

[extras-debug]
name=Circle Linux $releasever - Extras Debug
mirrorlist=https://mirrorlist.cclinux.org/mirrorlist?arch=$basearch&repo=extras-$releasever-debug
#baseurl=http://mirror.cclinux.org/$contentdir/$releasever/extras/$basearch/debug/tree/
gpgcheck=1
enabled=0
metadata_expire=6h
gpgkey=file:///usr/share/distribution-gpg-keys/circle/RPM-GPG-KEY-circleofficial

[extras-source]
name=Circle Linux $releasever - Extras Source
mirrorlist=https://mirrorlist.cclinux.org/mirrorlist?arch=$basearch&repo=extras-$releasever-source
#baseurl=http://mirror.cclinux.org/$contentdir/$releasever/extras/source/tree/
gpgcheck=1
enabled=0
metadata_expire=6h
gpgkey=file:///usr/share/distribution-gpg-keys/circle/RPM-GPG-KEY-circleofficial

[highavailability-debug]
name=Circle Linux $releasever - High Availability - Debug
mirrorlist=https://mirrorlist.cclinux.org/mirrorlist?arch=$basearch&repo=HighAvailability-$releasever-debug
#baseurl=http://mirror.cclinux.org/$contentdir/$releasever/HighAvailability/$basearch/debug/tree/
gpgcheck=1
enabled=0
metadata_expire=6h
gpgkey=file:///usr/share/distribution-gpg-keys/circle/RPM-GPG-KEY-circleofficial

[highavailability-source]
name=Circle Linux $releasever - High Availability - Source
mirrorlist=https://mirrorlist.cclinux.org/mirrorlist?arch=source&repo=HighAvailability-$releasever-source
#baseurl=http://mirror.cclinux.org/$contentdir/$releasever/HighAvailability/source/tree/
gpgcheck=1
enabled=0
metadata_expire=6h
gpgkey=file:///usr/share/distribution-gpg-keys/circle/RPM-GPG-KEY-circleofficial

[resilientstorage-debug]
name=Circle Linux $releasever - Resilient Storage - Debug
mirrorlist=https://mirrorlist.cclinux.org/mirrorlist?arch=$basearch&repo=ResilientStorage-$releasever-debug
#baseurl=http://mirror.cclinux.org/$contentdir/$releasever/ResilientStorage/$basearch/debug/tree/
gpgcheck=1
enabled=0
metadata_expire=6h
gpgkey=file:///usr/share/distribution-gpg-keys/circle/RPM-GPG-KEY-circleofficial

[resilientstorage-source]
name=Circle Linux $releasever - Resilient Storage - Source
mirrorlist=https://mirrorlist.cclinux.org/mirrorlist?arch=source&repo=ResilientStorage-$releasever-source
#baseurl=http://mirror.cclinux.org/$contentdir/$releasever/ResilientStorage/source/tree/
gpgcheck=1
enabled=0
metadata_expire=6h
gpgkey=file:///usr/share/distribution-gpg-keys/circle/RPM-GPG-KEY-circleofficial

[nfv-debug]
name=Circle Linux $releasever - NFV Debug
mirrorlist=https://mirrorlist.cclinux.org/mirrorlist?arch=$basearch&repo=NFV-$releasever-debug
#baseurl=http://mirror.cclinux.org/$contentdir/$releasever/NFV/$basearch/debug/tree/
gpgcheck=1
enabled=0
metadata_expire=6h
gpgkey=file:///usr/share/distribution-gpg-keys/circle/RPM-GPG-KEY-circleofficial

[nfv-source]
name=Circle Linux $releasever - NFV Source
mirrorlist=https://mirrorlist.cclinux.org/mirrorlist?arch=$basearch&repo=NFV-$releasever-source
#baseurl=http://mirror.cclinux.org/$contentdir/$releasever/NFV/source/tree/
gpgcheck=1
enabled=0
metadata_expire=6h
gpgkey=file:///usr/share/distribution-gpg-keys/circle/RPM-GPG-KEY-circleofficial

[rt-debug]
name=Circle Linux $releasever - Realtime Debug
mirrorlist=https://mirrorlist.cclinux.org/mirrorlist?arch=$basearch&repo=RT-$releasever-debug
#baseurl=http://mirror.cclinux.org/$contentdir/$releasever/RT/$basearch/debug/tree/
gpgcheck=1
enabled=0
metadata_expire=6h
gpgkey=file:///usr/share/distribution-gpg-keys/circle/RPM-GPG-KEY-circleofficial

[rt-source]
name=Circle Linux $releasever - Realtime Source
mirrorlist=https://mirrorlist.cclinux.org/mirrorlist?arch=$basearch&repo=RT-$releasever-source
#baseurl=http://mirror.cclinux.org/$contentdir/$releasever/RT/source/tree/
gpgcheck=1
enabled=0
metadata_expire=6h
gpgkey=file:///usr/share/distribution-gpg-keys/circle/RPM-GPG-KEY-circleofficial


"""
