config_opts['chroot_setup_cmd'] = 'install tar gcc-c++ redhat-rpm-config redhat-release which xz sed make bzip2 gzip gcc coreutils unzip diffutils cpio bash gawk rpm-build info patch util-linux findutils grep'
config_opts['dist'] = 'el8'  # only useful for --resultdir variable subst
config_opts['releasever'] = '8'
config_opts['package_manager'] = 'dnf'
config_opts['extra_chroot_dirs'] = [ '/run/lock', ]
config_opts['bootstrap_image'] = 'docker.io/circlelinuxos/circlelinux:8'
# Relates: https://github.com/rpm-software-management/mock/issues/1170
config_opts['use_bootstrap_image'] = False


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
module_platform_id=platform:el8
user_agent={{ user_agent }}
tsflags=nodocs


[baseos]
name=Circle Linux $releasever - BaseOS
mirrorlist=https://mirrorlist.cclinux.org/mirrorlist?arch=$basearch&repo=BaseOS
#baseurl=https://mirror.cclinux.org/$contentdir/$releasever/BaseOS/$basearch/os/
gpgcheck=1
enabled=1
gpgkey=file:///usr/share/distribution-gpg-keys/circle/RPM-GPG-KEY-circleofficial

[appstream]
name=Circle Linux $releasever - AppStream
mirrorlist=https://mirrorlist.cclinux.org/mirrorlist?arch=$basearch&repo=AppStream
#baseurl=https://mirror.cclinux.org/$contentdir/$releasever/AppStream/$basearch/os/
gpgcheck=1
enabled=1
gpgkey=file:///usr/share/distribution-gpg-keys/circle/RPM-GPG-KEY-circleofficial

[powertools]
name=Circle Linux $releasever - PowerTools
mirrorlist=https://mirrorlist.cclinux.org/mirrorlist?arch=$basearch&repo=PowerTools
#baseurl=https://mirror.cclinux.org/$contentdir/$releasever/PowerTools/$basearch/os/
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/circle/RPM-GPG-KEY-circleofficial

[extras]
name=Circle Linux $releasever - Extras
mirrorlist=https://mirrorlist.cclinux.org/mirrorlist?arch=$basearch&repo=extras
#baseurl=https://mirror.cclinux.org/$contentdir/$releasever/extras/$basearch/os/
gpgcheck=1
enabled=1
gpgkey=file:///usr/share/distribution-gpg-keys/circle/RPM-GPG-KEY-circleofficial

[devel]
name=Circle Linux $releasever - Devel WARNING! FOR BUILDROOT USE ONLY!
mirrorlist=https://mirrorlist.cclinux.org/mirrorlist?arch=$basearch&repo=Devel-$releasever
#baseurl=https://mirror.cclinux.org/$contentdir/$releasever/Devel/$basearch/os/
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/circle/RPM-GPG-KEY-circleofficial

[baseos-debug]
name=Circle Linux $releasever - BaseOS  Debug
mirrorlist=https://mirrorlist.cclinux.org/mirrorlist?arch=$basearch&repo=BaseOS-debug
#baseurl=https://mirror.cclinux.org/$contentdir/$releasever/BaseOS/$basearch/debug/tree/
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/circle/RPM-GPG-KEY-circleofficial

[appstream-debug]
name=Circle Linux $releasever - AppStream  Debug
mirrorlist=https://mirrorlist.cclinux.org/mirrorlist?arch=$basearch&repo=AppStream-debug
#baseurl=https://mirror.cclinux.org/$contentdir/$releasever/AppStream/$basearch/debug/tree/
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/circle/RPM-GPG-KEY-circleofficial

[powertools-debug]
name=Circle Linux $releasever - PowerTools  Debug
mirrorlist=https://mirrorlist.cclinux.org/mirrorlist?arch=$basearch&repo=PowerTools-debug
#baseurl=https://mirror.cclinux.org/$contentdir/$releasever/PowerTools/$basearch/debug/tree/
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/circle/RPM-GPG-KEY-circleofficial

[extras-debug]
name=Circle Linux $releasever - Extras  Debug
mirrorlist=https://mirrorlist.cclinux.org/mirrorlist?arch=$basearch&repo=extras-debug
#baseurl=https://mirror.cclinux.org/$contentdir/$releasever/extras/$basearch/debug/tree
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/circle/RPM-GPG-KEY-circleofficial

[devel-debug]
name=Circle Linux $releasever - Devel  Debug
mirrorlist=https://mirrorlist.cclinux.org/mirrorlist?arch=$basearch&repo=Devel-$releasever
#baseurl=https://mirror.cclinux.org/$contentdir/$releasever/Devel/$basearch/debug/tree
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/circle/RPM-GPG-KEY-circleofficial

[baseos-source]
name=Circle Linux $releasever - BaseOS  Source
mirrorlist=https://mirrorlist.cclinux.org/mirrorlist?arch=source&repo=BaseOS
#baseurl=https://mirror.cclinux.org/$contentdir/$releasever/BaseOS/source/tree/
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/circle/RPM-GPG-KEY-circleofficial

[appstream-source]
name=Circle Linux $releasever - AppStream  Source
mirrorlist=https://mirrorlist.cclinux.org/mirrorlist?arch=source&repo=AppStream
#baseurl=https://mirror.cclinux.org/$contentdir/$releasever/AppStream/source/tree/
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/circle/RPM-GPG-KEY-circleofficial

[extras-source]
name=Circle Linux $releasever - Extras  Source
mirrorlist=https://mirrorlist.cclinux.org/mirrorlist?arch=source&repo=extras
#baseurl=https://mirror.cclinux.org/$contentdir/$releasever/extras/source/tree/
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/circle/RPM-GPG-KEY-circleofficial

[powertools-source]
name=Circle Linux $releasever - PowerTools  Source
mirrorlist=https://mirrorlist.cclinux.org/mirrorlist?arch=source&repo=PowerTools
#baseurl=https://mirror.cclinux.org/$contentdir/$releasever/PowerTools/source/tree/
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/circle/RPM-GPG-KEY-circleofficial

[devel-source]
name=Circle Linux $releasever - Devel  Source
mirrorlist=https://mirrorlist.cclinux.org/mirrorlist?arch=source&repo=Devel-$releasever
#baseurl=https://mirror.cclinux.org/$contentdir/$releasever/Devel/source/os/
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/circle/RPM-GPG-KEY-circleofficial

"""
