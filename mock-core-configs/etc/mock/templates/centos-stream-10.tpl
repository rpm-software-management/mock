config_opts['chroot_setup_cmd'] = 'install bash bzip2 centos-stream-release coreutils cpio diffutils findutils gawk glibc-minimal-langpack grep gzip info patch redhat-rpm-config rpm-build sed shadow-utils tar unzip util-linux which xz'
config_opts['dist'] = 'el10'  # only useful for --resultdir variable subst
config_opts['releasever'] = '10'
config_opts['releasever_major'] = '10'
config_opts['package_manager'] = 'dnf'
config_opts['extra_chroot_dirs'] = [ '/run/lock', ]
config_opts['description'] = 'CentOS Stream 10'

config_opts['bootstrap_image'] = 'quay.io/centos/centos:stream10'
config_opts['bootstrap_image_ready'] = True

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
best=1
install_weak_deps=0
protected_packages=
skip_if_unavailable=False
module_platform_id=platform:el10
user_agent={{ user_agent }}

{% if koji_primary_repo != None and koji_primary_repo != "centos-stream" %}
[local-centos-stream]
{% else %}
[local]
{% endif %}
name=CentOS Stream $releasever - Koji Local - BUILDROOT ONLY!
baseurl=https://kojihub.stream.centos.org/kojifiles/repos/c{{ releasever }}s-build/latest/$basearch/
cost=2000
enabled=0

[baseos]
name=CentOS Stream $releasever - BaseOS
#baseurl=http://mirror.stream.centos.org/$releasever-stream/BaseOS/$basearch/os/
metalink=https://mirrors.centos.org/metalink?repo=centos-baseos-$releasever-stream&arch=$basearch&protocol=https,http
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official-SHA256
gpgcheck=1
countme=1
enabled=1

[appstream]
name=CentOS Stream $releasever - AppStream
#baseurl=http://mirror.stream.centos.org/$releasever-stream/AppStream/$basearch/os/
metalink=https://mirrors.centos.org/metalink?repo=centos-appstream-$releasever-stream&arch=$basearch&protocol=https,http
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official-SHA256
gpgcheck=1
countme=1
enabled=1

[crb]
name=CentOS Stream $releasever - CRB
#baseurl=http://mirror.stream.centos.org/$releasever-stream/CRB/$basearch/os/
metalink=https://mirrors.centos.org/metalink?repo=centos-crb-$releasever-stream&arch=$basearch&protocol=https,http
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official-SHA256
gpgcheck=1
countme=1
enabled=1

[extras-common]
name=CentOS Stream $releasever - Extras packages
#baseurl=http://mirror.stream.centos.org/SIGs/$releasever-stream/extras/$basearch/extras-common/
metalink=https://mirrors.centos.org/metalink?repo=centos-extras-sig-extras-common-$releasever-stream&arch=$basearch&protocol=https,http
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-SIG-Extras-SHA512
gpgcheck=1
enabled=1
skip_if_unavailable=False

[baseos-debuginfo]
name=CentOS Stream $releasever - BaseOS - Debug
#baseurl=https://composes.stream.centos.org/stream-10/production/latest-CentOS-Stream/compose/BaseOS/$basearch/debug/tree/
metalink=https://mirrors.centos.org/metalink?repo=centos-baseos-debug-$releasever-stream&arch=$basearch&protocol=https,http
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official-SHA256
gpgcheck=1
enabled=0

[baseos-source]
name=CentOS Stream $releasever - BaseOS - Source
#baseurl=https://composes.stream.centos.org/stream-10/production/latest-CentOS-Stream/compose/BaseOS/source/tree/
metalink=https://mirrors.centos.org/metalink?repo=centos-baseos-source-$releasever-stream&arch=source&protocol=https,http
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official-SHA256
gpgcheck=1
enabled=0

[appstream-debuginfo]
name=CentOS Stream $releasever - AppStream - Debug
#baseurl=https://composes.stream.centos.org/stream-10/production/latest-CentOS-Stream/compose/AppStream/$basearch/debug/tree/
metalink=https://mirrors.centos.org/metalink?repo=centos-appstream-debug-$releasever-stream&arch=$basearch&protocol=https,http
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official-SHA256
gpgcheck=1
enabled=0

[appstream-source]
name=CentOS Stream $releasever - AppStream - Source
#baseurl=https://composes.stream.centos.org/stream-10/production/latest-CentOS-Stream/compose/AppStream/source/tree/
metalink=https://mirrors.centos.org/metalink?repo=centos-appstream-source-$releasever-stream&arch=source&protocol=https,http
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official-SHA256
gpgcheck=1
enabled=0

[crb-debuginfo]
name=CentOS Stream $releasever - CRB - Debug
#baseurl=https://composes.stream.centos.org/stream-10/production/latest-CentOS-Stream/compose/CRB/$basearch/debug/tree/
metalink=https://mirrors.centos.org/metalink?repo=centos-crb-debug-$releasever-stream&arch=$basearch&protocol=https,http
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official-SHA256
gpgcheck=1
enabled=0

[crb-source]
name=CentOS Stream $releasever - CRB - Source
#baseurl=https://composes.stream.centos.org/stream-10/production/latest-CentOS-Stream/compose/CRB/source/tree/
metalink=https://mirrors.centos.org/metalink?repo=centos-crb-source-$releasever-stream&arch=source&protocol=https,http
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official-SHA256
gpgcheck=1
enabled=0
"""
