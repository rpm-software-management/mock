config_opts['chroot_setup_cmd'] = 'install tar gcc-c++ redhat-rpm-config redhat-release which xz sed make bzip2 gzip gcc coreutils unzip shadow-utils diffutils cpio bash gawk rpm-build info patch util-linux findutils grep'
config_opts['dist'] = 'el8'  # only useful for --resultdir variable subst
config_opts['releasever'] = '8'
config_opts['package_manager'] = 'dnf'
config_opts['extra_chroot_dirs'] = [ '/run/lock', ]
config_opts['bootstrap_image'] = 'quay.io/centos/centos:8'


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

[baseos]
name=CentOS Linux $releasever - BaseOS
mirrorlist=http://mirrorlist.centos.org/?release=8&arch=$basearch&repo=BaseOS&infra=$infra
failovermethod=priority
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official
gpgcheck=1
skip_if_unavailable=False

[appstream]
name=CentOS Linux $releasever - AppStream
mirrorlist=http://mirrorlist.centos.org/?release=8&arch=$basearch&repo=AppStream&infra=$infra
#baseurl=http://mirror.centos.org/centos/$releasever/AppStream/$basearch/os/
gpgcheck=1
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official

[powertools]
name=CentOS Linux $releasever - PowerTools
mirrorlist=http://mirrorlist.centos.org/?release=8&arch=$basearch&repo=PowerTools&infra=$infra
#baseurl=http://mirror.centos.org/centos/$releasever/PowerTools/$basearch/os/
gpgcheck=1
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official

[devel]
name=CentOS Linux $releasever - Devel WARNING! FOR BUILDROOT USE ONLY!
mirrorlist=http://mirrorlist.centos.org/?release=$releasever&arch=$basearch&repo=Devel&infra=$infra
#baseurl=http://mirror.centos.org/$contentdir/$releasever/Devel/$basearch/os/
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official

[plus]
name=CentOS Linux $releasever - Plus
mirrorlist=http://mirrorlist.centos.org/?release=8&arch=$basearch&repo=centosplus&infra=$infra
#baseurl=http://mirror.centos.org/centos/$releasever/centosplus/$basearch/os/
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official

[cr]
name=CentOS Linux $releasever - ContinuousRelease
baseurl=http://mirror.centos.org/centos/8/cr/$basearch/os/
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official

[debuginfo]
name=CentOS Linux $releasever - Debuginfo
baseurl=http://debuginfo.centos.org/8/$basearch/
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official

[extras]
name=CentOS Linux $releasever - Extras
mirrorlist=http://mirrorlist.centos.org/?release=8&arch=$basearch&repo=extras&infra=$infra
#baseurl=http://mirror.centos.org/centos/$releasever/extras/$basearch/os/
gpgcheck=1
enabled=1
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official

[fasttrack]
name=CentOS Linux $releasever - FastTrack
mirrorlist=http://mirrorlist.centos.org/?release=8&arch=$basearch&repo=fasttrack&infra=$infra
#baseurl=http://mirror.centos.org/centos/$releasever/fasttrack/$basearch/os/
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official

[baseos-source]
name=CentOS Linux $releasever - BaseOS - Source
baseurl=http://vault.centos.org/centos/8/BaseOS/Source/
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official

[appstream-source]
name=CentOS Linux $releasever - AppStream - Source
baseurl=http://vault.centos.org/centos/8/AppStream/Source/
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official

[powertools-source]
name=CentOS Linux $releasever - PowerTools - Source
baseurl=http://vault.centos.org/centos/8/PowerTools/Source/
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official

[extras-source]
name=CentOS Linux $releasever - Extras - Source
baseurl=http://vault.centos.org/centos/8/extras/Source/
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official

[plus-source]
name=CentOS Linux $releasever - Plus - Source
baseurl=http://vault.centos.org/centos/8/centosplus/Source/
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official
"""
