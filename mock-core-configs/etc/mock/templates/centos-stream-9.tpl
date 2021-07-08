config_opts['chroot_setup_cmd'] = 'install tar gcc-c++ redhat-rpm-config redhat-release which xz sed make bzip2 gzip gcc coreutils unzip shadow-utils diffutils cpio bash gawk rpm-build info patch util-linux findutils grep'
config_opts['dist'] = 'el9'  # only useful for --resultdir variable subst
config_opts['releasever'] = '9'
config_opts['package_manager'] = 'dnf'
config_opts['extra_chroot_dirs'] = [ '/run/lock', ]

# TODO: flip to 'stream9' tag once available
config_opts['bootstrap_image'] = 'quay.io/centos/centos:stream9-development'

config_opts['dnf.conf'] = """
[main]
keepcache=1
debuglevel=2
reposdir=/dev/null
logfile=/var/log/yum.log
retries=20
obsoletes=1
gpgcheck=1
assumeyes=1
syslog_ident=mock
syslog_device=
mdpolicy=group:primary
best=1
protected_packages=
module_platform_id=platform:el9
user_agent={{ user_agent }}

[baseos-pre-release]
name=CentOS Stream $releasever - BaseOS (pre-release)
baseurl=https://composes.stream.centos.org/production/latest-CentOS-Stream/compose/BaseOS/$basearch/os/
failovermethod=priority
#gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official
gpgcheck=0
skip_if_unavailable=False

[appstream-pre-release]
name=CentOS Stream $releasever - AppStream (pre-release)
baseurl=https://composes.stream.centos.org/production/latest-CentOS-Stream/compose/AppStream/$basearch/os/
enabled=1
#gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official
gpgcheck=0

[crb-pre-release]
name=CentOS Stream $releasever - CRB (pre-release)
baseurl=https://composes.stream.centos.org/production/latest-CentOS-Stream/compose/CRB/$basearch/os/
enabled=1
#gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official
gpgcheck=0
"""
