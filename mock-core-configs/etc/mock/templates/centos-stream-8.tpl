config_opts['chroot_setup_cmd'] = 'install tar gcc-c++ redhat-rpm-config redhat-release which xz sed make bzip2 gzip gcc coreutils unzip shadow-utils diffutils cpio bash gawk rpm-build info patch util-linux findutils grep'
config_opts['dist'] = 'el8'  # only useful for --resultdir variable subst
config_opts['releasever'] = '8'
config_opts['package_manager'] = 'dnf'
config_opts['extra_chroot_dirs'] = [ '/run/lock', ]
config_opts['bootstrap_image'] = 'quay.io/centos/centos:stream8'
config_opts['dnf_vars'] = { 'stream': '8-stream',
                            'contentdir': 'centos',
                            'infra': 'stock',
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
baseurl=https://koji.mbox.centos.org/kojifiles/repos/dist-c$stream-build/latest/$basearch/
cost=2000
enabled=0
skip_if_unavailable=False

[baseos]
name=CentOS Stream $releasever - BaseOS
mirrorlist=http://mirrorlist.centos.org/?release=$stream&arch=$basearch&repo=BaseOS&infra=$infra
#baseurl=http://mirror.centos.org/$contentdir/$stream/BaseOS/$basearch/os/
gpgcheck=1
enabled=1
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official

[appstream]
name=CentOS Stream $releasever - AppStream
mirrorlist=http://mirrorlist.centos.org/?release=$stream&arch=$basearch&repo=AppStream&infra=$infra
#baseurl=http://mirror.centos.org/$contentdir/$stream/AppStream/$basearch/os/
gpgcheck=1
enabled=1
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official

[debuginfo]
name=CentOS Stream $releasever - Debuginfo
baseurl=http://debuginfo.centos.org/$stream/$basearch/
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official

[extras]
name=CentOS Stream $releasever - Extras
mirrorlist=http://mirrorlist.centos.org/?release=$stream&arch=$basearch&repo=extras&infra=$infra
#baseurl=http://mirror.centos.org/$contentdir/$stream/extras/$basearch/os/
gpgcheck=1
enabled=1
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official

[powertools]
name=CentOS Stream $releasever - PowerTools
mirrorlist=http://mirrorlist.centos.org/?release=$stream&arch=$basearch&repo=PowerTools&infra=$infra
#baseurl=http://mirror.centos.org/$contentdir/$stream/PowerTools/$basearch/os/
gpgcheck=1
enabled=1
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official

[rt]
name=CentOS Stream $releasever - RealTime
mirrorlist=http://mirrorlist.centos.org/?release=$stream&arch=$basearch&repo=RT&infra=$infra
#baseurl=http://mirror.centos.org/$contentdir/$stream/RT/$basearch/os/
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official

[ha]
name=CentOS Stream $releasever - HighAvailability
mirrorlist=http://mirrorlist.centos.org/?release=$stream&arch=$basearch&repo=HighAvailability&infra=$infra
#baseurl=http://mirror.centos.org/$contentdir/$stream/HighAvailability/$basearch/os/
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official

[resilientstorage]
name=CentOS Stream $releasever - ResilientStorage
mirrorlist=http://mirrorlist.centos.org/?release=$stream&arch=$basearch&repo=ResilientStorage&infra=$infra
#baseurl=http://mirror.centos.org/$contentdir/$stream/ResilientStorage/$basearch/os/
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official

[baseos-source]
name=CentOS Stream $releasever - BaseOS - Source
baseurl=http://vault.centos.org/$contentdir/$stream/BaseOS/Source/
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official

[appstream-source]
name=CentOS Stream $releasever - AppStream - Source
baseurl=http://vault.centos.org/$contentdir/$stream/AppStream/Source/
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official

[powertools-source]
name=CentOS Stream $releasever - PowerTools - Source
baseurl=http://vault.centos.org/$contentdir/$stream/PowerTools/Source/
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official

[extras-source]
name=CentOS Stream $releasever - Extras - Source
baseurl=http://vault.centos.org/$contentdir/$stream/extras/Source/
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official

[ha-source]
name=CentOS Stream $releasever - HighAvailability - Source
baseurl=http://vault.centos.org/$contentdir/$stream/HighAvailability/Source/
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official

[rt-source]
name=CentOS Stream $releasever - RT - Source
baseurl=http://vault.centos.org/$contentdir/$stream/RT/Source/
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official

[resilientstorage-source]
name=CentOS Stream $releasever - ResilientStorage - Source
baseurl=http://vault.centos.org/$contentdir/$stream/ResilientStorage/Source/
gpgcheck=1
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official
"""
