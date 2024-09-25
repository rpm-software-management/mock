config_opts['chroot_setup_cmd'] = 'install tar gcc-c++ redhat-rpm-config anolis-release which xz sed make bzip2 gzip gcc coreutils unzip diffutils cpio bash gawk rpm-build info patch util-linux findutils grep'
config_opts['dist'] = 'an8'  # only useful for --resultdir variable subst
config_opts['releasever'] = '8'
config_opts['package_manager'] = 'dnf'
config_opts['description'] = 'Anolis 8'
config_opts['extra_chroot_dirs'] = [ '/run/lock', ]

config_opts['bootstrap_image'] = 'docker.io/openanolis/anolisos:8'

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
module_platform_id=platform:an8
user_agent={{ user_agent }}
tsflags=nodocs

[BaseOS]
name=AnolisOS-$releasever - BaseOS
baseurl=http://mirrors.openanolis.cn/anolis/$releasever/BaseOS/$basearch/os
enabled=1
gpgkey=file:///usr/share/distribution-gpg-keys/anolis/RPM-GPG-KEY-ANOLIS
gpgcheck=1

[AppStream]
name=AnolisOS-$releasever - AppStream
baseurl=http://mirrors.openanolis.cn/anolis/$releasever/AppStream/$basearch/os
enabled=1
gpgkey=file:///usr/share/distribution-gpg-keys/anolis/RPM-GPG-KEY-ANOLIS
gpgcheck=1

[PowerTools]
name=AnolisOS-$releasever - PowerTools
baseurl=http://mirrors.openanolis.cn/anolis/$releasever/PowerTools/$basearch/os
enabled=1
gpgkey=file:///usr/share/distribution-gpg-keys/anolis/RPM-GPG-KEY-ANOLIS
gpgcheck=1
"""
