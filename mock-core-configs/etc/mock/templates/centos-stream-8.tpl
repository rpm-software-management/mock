config_opts['chroot_setup_cmd'] = 'install tar gcc-c++ redhat-rpm-config redhat-release which xz sed make bzip2 gzip gcc coreutils unzip shadow-utils diffutils cpio bash gawk rpm-build info patch util-linux findutils grep'
config_opts['dist'] = 'el8'  # only useful for --resultdir variable subst
config_opts['releasever'] = '8'
config_opts['package_manager'] = 'dnf'
config_opts['extra_chroot_dirs'] = [ '/run/lock', ]
config_opts['bootstrap_image'] = 'quay.io/centos/centos:stream8'
config_opts['dnf_vars'] = { 'stream': '8-stream',
                            'contentdir': 'centos',
                          }

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
mdpolicy=group:primary
best=1
install_weak_deps=0
protected_packages=
module_platform_id=platform:el8
user_agent={{ user_agent }}

{% if koji_primary_repo != None and koji_primary_repo != "centos-stream" %}
[local-centos-stream]
{% else %}
[local]
{% endif %}
name=CentOS Stream $releasever - Koji Local - BUILDROOT ONLY!
baseurl=https://koji.mbox.centos.org/kojifiles/repos/dist-c{{ releasever }}-stream-build/latest/$basearch/
cost=2000
enabled=0
skip_if_unavailable=False

[baseos]
name=CentOS Stream $releasever - BaseOS
mirrorlist=http://mirrorlist.centos.org/?release=$releasever-stream&arch=$basearch&repo=BaseOS&infra=$infra
#baseurl=http://mirror.centos.org/centos/$releasever-stream/BaseOS/$basearch/os/
failovermethod=priority
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official
gpgcheck=1
skip_if_unavailable=False

[appstream]
name=CentOS Stream $releasever - AppStream
mirrorlist=http://mirrorlist.centos.org/?release=$releasever-stream&arch=$basearch&repo=AppStream&infra=$infra
#baseurl=http://mirror.centos.org/centos/$releasever-stream/AppStream/$basearch/os/
gpgcheck=1
enabled=1
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official

[debuginfo]
name=CentOS Stream $releasever - Debuginfo
baseurl=http://debuginfo.centos.org/$releasever-stream/$basearch/
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official

[Stream-centosplus]
name=CentOS-Stream - Plus
baseurl=http://mirror.centos.org/centos/$releasever-stream/centosplus/$basearch/os/
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official

[cr]
name=CentOS-$releasever - cr
baseurl=http://mirror.centos.org/centos/$releasever/cr/$basearch/os/
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official

[Stream-base-debuginfo]
name=CentOS-Stream - Debuginfo
baseurl=http://debuginfo.centos.org/$releasever-stream/$basearch/
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official

[extras]
name=CentOS Stream $releasever - Extras
mirrorlist=http://mirrorlist.centos.org/?release=$releasever-stream&arch=$basearch&repo=extras&infra=$infra
#baseurl=http://mirror.centos.org/centos/$releasever-stream/extras/$basearch/os/
gpgcheck=1
enabled=1
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official

[powertools]
name=CentOS Stream $releasever - PowerTools
mirrorlist=http://mirrorlist.centos.org/?release=$releasever-stream&arch=$basearch&repo=PowerTools&infra=$infra
#baseurl=http://mirror.centos.org/centos/$releasever-stream/PowerTools/$basearch/os/
gpgcheck=1
enabled=1
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official

[rt]
name=CentOS Stream $releasever - RealTime
mirrorlist=http://mirrorlist.centos.org/?release=$releasever-stream&arch=$basearch&repo=RT&infra=$infra
#baseurl=http://mirror.centos.org/centos/$releasever-stream/RT/$basearch/os/
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official

[ha]
name=CentOS Stream $releasever - HighAvailability
mirrorlist=http://mirrorlist.centos.org/?release=$releasever-stream&arch=$basearch&repo=HighAvailability&infra=$infra
#baseurl=http://mirror.centos.org/centos/$releasever-stream/HighAvailability/$basearch/os/
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official

[Stream-Devel]
name=CentOS-Stream - Devel (WARNING: UNSUPPORTED - FOR BUILDROOT USE ONLY!)
baseurl=http://mirror.centos.org/centos/$releasever-stream/Devel/$basearch/os/
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official

[Stream-BaseOS-source]
name=CentOS-Stream - BaseOS Sources
baseurl=http://vault.centos.org/centos/$releasever-stream/BaseOS/Source/
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official

[Stream-AppStream-source]
name=CentOS-Stream - AppStream Sources
baseurl=http://vault.centos.org/centos/$releasever-stream/AppStream/Source/
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official

[Stream-PowerTools-source]
name=CentOS-Stream - PowerTools Sources
baseurl=http://vault.centos.org/centos/$releasever-stream/PowerTools/Source/
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official

[Stream-extras-source]
name=CentOS-Stream - Extras Sources
baseurl=http://vault.centos.org/centos/$releasever-stream/extras/Source/
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official

[Stream-centosplus-source]
name=CentOS-Stream - Plus Sources
baseurl=http://vault.centos.org/centos/$releasever-stream/centosplus/Source/
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official
"""
