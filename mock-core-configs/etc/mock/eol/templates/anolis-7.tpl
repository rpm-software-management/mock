config_opts['chroot_setup_cmd'] = 'install bash bzip2 coreutils cpio diffutils findutils gawk gcc gcc-c++ grep gzip info make patch redhat-rpm-config anolis-release rpm-build sed tar unzip util-linux which xz'

config_opts['dist'] = 'an7'  # only useful for --resultdir variable subst
config_opts['releasever'] = '7'
config_opts['package_manager'] = 'yum'
config_opts['description'] = 'Anolis 7'

# No v7 image https://hub.docker.com/r/openanolis/anolisos ?
config_opts['use_bootstrap_image'] = False

config_opts['yum.conf'] = """
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
protected_packages=
user_agent={{ user_agent }}

# repos

[os]
name=AnolisOS-7 - os
baseurl=http://mirrors.openanolis.cn/anolis/7/os/$basearch/os
enabled=1
gpgkey=file:///usr/share/distribution-gpg-keys/anolis/RPM-GPG-KEY-ANOLIS
gpgcheck=1

[updates]
name=AnolisOS-7 - updates
baseurl=http://mirrors.openanolis.cn/anolis/7/updates/$basearch/os
enabled=1
gpgkey=file:///usr/share/distribution-gpg-keys/anolis/RPM-GPG-KEY-ANOLIS
gpgcheck=1

[extras]
name=AnolisOS-7 - extras
baseurl=http://mirrors.openanolis.cn/anolis/7/extras/$basearch/os
enabled=1
gpgkey=file:///usr/share/distribution-gpg-keys/anolis/RPM-GPG-KEY-ANOLIS
gpgcheck=1
"""
