config_opts['chroot_setup_cmd'] = 'install tar gcc-c++ redhat-rpm-config redhat-release which xz sed make bzip2 gzip gcc coreutils unzip diffutils cpio bash gawk rpm-build info patch util-linux findutils grep'
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
name=CentOS-$releasever - Base
baseurl=http://vault.centos.org/centos/$releasever/BaseOS/$basearch/os/
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official
gpgcheck=1
skip_if_unavailable=False

[appstream]
name=CentOS-$releasever - AppStream
baseurl=http://vault.centos.org/centos/$releasever/AppStream/$basearch/os/
gpgcheck=1
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official

[powertools]
name=CentOS-$releasever - PowerTools
baseurl=http://vault.centos.org/centos/$releasever/PowerTools/$basearch/os/
gpgcheck=1
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official

[devel]
name=CentOS-$releasever - Devel (WARNING: UNSUPPORTED - FOR BUILDROOT USE ONLY!)
baseurl=http://vault.centos.org/centos/$releasever/Devel/$basearch/os/
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official

[plus]
name=CentOS-$releasever - Plus
baseurl=http://vault.centos.org/centos/$releasever/centosplus/$basearch/os/
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official

[cr]
name=CentOS-$releasever - cr
baseurl=http://vault.centos.org/centos/$releasever/cr/$basearch/os/
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official

[debuginfo]
name=CentOS-$releasever - Debuginfo
baseurl=http://debuginfo.centos.org/8/$basearch/
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official

[extras]
name=CentOS-$releasever - Extras
baseurl=https://vault.centos.org/centos/$releasever/extras/$basearch/os/
gpgcheck=1
enabled=1
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official

[fasttrack]
name=CentOS-$releasever - fasttrack
baseurl=https://vault.centos.org/centos/$releasever/fasttrack/$basearch/os/
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official

[baseos-source]
name=CentOS-$releasever - BaseOS Sources
baseurl=http://vault.centos.org/centos/$releasever/BaseOS/Source/
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official

[appstream-source]
name=CentOS-$releasever - AppStream Sources
baseurl=http://vault.centos.org/centos/$releasever/AppStream/Source/
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official

[powertools-source]
name=CentOS-$releasever - PowerTools Sources
baseurl=http://vault.centos.org/centos/$releasever/PowerTools/Source/
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official

[extras-source]
name=CentOS-$releasever - Extras Sources
baseurl=http://vault.centos.org/centos/$releasever/extras/Source/
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official

[splus-source]
name=CentOS-$releasever - Plus Sources
baseurl=http://vault.centos.org/centos/$releasever/centosplus/Source/
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official
"""
