config_opts['chroot_setup_cmd'] = 'install bash bzip2 centos-stream-release coreutils cpio diffutils findutils gawk glibc-minimal-langpack grep gzip info patch redhat-rpm-config rpm-build sed shadow-utils tar unzip util-linux which xz'
config_opts['dist'] = 'el10'  # only useful for --resultdir variable subst
config_opts['releasever'] = '10'
config_opts['package_manager'] = 'dnf'
config_opts['extra_chroot_dirs'] = [ '/run/lock', ]
config_opts['description'] = 'CentOS Stream 10'

config_opts['use_bootstrap_image'] = False
config_opts['bootstrap_image'] = 'quay.io/centos/centos:stream10'

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
best=1
install_weak_deps=0
protected_packages=
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
skip_if_unavailable=False

[baseos]
name=CentOS Stream $releasever - BaseOS
baseurl=https://composes.stream.centos.org/stream-10/production/latest-CentOS-Stream/compose/BaseOS/$basearch/os
#metalink=https://mirrors.centos.org/metalink?repo=centos-baseos-$stream&arch=$basearch&protocol=https,http
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official-SHA256
gpgcheck=1
repo_gpgcheck=0
metadata_expire=6h
countme=1
enabled=1

[baseos-debuginfo]
name=CentOS Stream $releasever - BaseOS - Debug
baseurl=https://composes.stream.centos.org/stream-10/production/latest-CentOS-Stream/compose/BaseOS/$basearch/debug/tree/
#metalink=https://mirrors.centos.org/metalink?repo=centos-baseos-debug-$stream&arch=$basearch&protocol=https,http
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official-SHA256
gpgcheck=1
repo_gpgcheck=0
metadata_expire=6h
enabled=0

[baseos-source]
name=CentOS Stream $releasever - BaseOS - Source
baseurl=https://composes.stream.centos.org/stream-10/production/latest-CentOS-Stream/compose/BaseOS/source/tree/
#metalink=https://mirrors.centos.org/metalink?repo=centos-baseos-source-$stream&arch=source&protocol=https,http
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official-SHA256
gpgcheck=1
repo_gpgcheck=0
metadata_expire=6h
enabled=0

[appstream]
name=CentOS Stream $releasever - AppStream
baseurl=https://composes.stream.centos.org/stream-10/production/latest-CentOS-Stream/compose/AppStream/$basearch/os
#metalink=https://mirrors.centos.org/metalink?repo=centos-appstream-$stream&arch=$basearch&protocol=https,http
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official-SHA256
gpgcheck=1
repo_gpgcheck=0
metadata_expire=6h
countme=1
enabled=1

[appstream-debuginfo]
name=CentOS Stream $releasever - AppStream - Debug
baseurl=https://composes.stream.centos.org/stream-10/production/latest-CentOS-Stream/compose/AppStream/$basearch/debug/tree/
#metalink=https://mirrors.centos.org/metalink?repo=centos-appstream-debug-$stream&arch=$basearch&protocol=https,http
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official-SHA256-SHA256
gpgcheck=1
repo_gpgcheck=0
metadata_expire=6h
enabled=0

[appstream-source]
name=CentOS Stream $releasever - AppStream - Source
baseurl=https://composes.stream.centos.org/stream-10/production/latest-CentOS-Stream/compose/AppStream/source/tree/
#metalink=https://mirrors.centos.org/metalink?repo=centos-appstream-source-$stream&arch=source&protocol=https,http
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official-SHA256
gpgcheck=1
repo_gpgcheck=0
metadata_expire=6h
enabled=0

[crb]
name=CentOS Stream $releasever - CRB
baseurl=https://composes.stream.centos.org/stream-10/production/latest-CentOS-Stream/compose/CRB/$basearch/os
#metalink=https://mirrors.centos.org/metalink?repo=centos-crb-$stream&arch=$basearch&protocol=https,http
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official-SHA256
gpgcheck=1
repo_gpgcheck=0
metadata_expire=6h
countme=1
enabled=1

[crb-debuginfo]
name=CentOS Stream $releasever - CRB - Debug
baseurl=https://composes.stream.centos.org/stream-10/production/latest-CentOS-Stream/compose/CRB/$basearch/debug/tree/
#metalink=https://mirrors.centos.org/metalink?repo=centos-crb-debug-$stream&arch=$basearch&protocol=https,http
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official-SHA256
gpgcheck=1
repo_gpgcheck=0
metadata_expire=6h
enabled=0

[crb-source]
name=CentOS Stream $releasever - CRB - Source
baseurl=https://composes.stream.centos.org/stream-10/production/latest-CentOS-Stream/compose/CRB/source/tree/
#metalink=https://mirrors.centos.org/metalink?repo=centos-crb-source-$stream&arch=source&protocol=https,http
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official-SHA256
gpgcheck=1
repo_gpgcheck=0
metadata_expire=6h
enabled=0
"""
