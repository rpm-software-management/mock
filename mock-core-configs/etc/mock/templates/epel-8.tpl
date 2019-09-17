config_opts['chroot_setup_cmd'] = 'install @buildsys-build'
config_opts['dist'] = 'el8'  # only useful for --resultdir variable subst
config_opts['releasever'] = '8'
config_opts['yum_install_command'] += ' --disablerepo=sclo*'

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
mdpolicy=group:primary
best=1
protected_packages=

# repos
[base]
name=BaseOS
mirrorlist=http://mirrorlist.centos.org/?release=8&arch=$basearch&repo=os
failovermethod=priority
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official
gpgcheck=1
skip_if_unavailable=False

[updates]
name=updates
enabled=1
mirrorlist=http://mirrorlist.centos.org/?release=8&arch=$basearch&repo=updates
failovermethod=priority
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official
gpgcheck=1
skip_if_unavailable=False

[epel]
name=epel
mirrorlist=http://mirrors.fedoraproject.org/mirrorlist?repo=epel-8&arch=$basearch
failovermethod=priority
gpgkey=file:///usr/share/distribution-gpg-keys/epel/RPM-GPG-KEY-EPEL-8
gpgcheck=1
skip_if_unavailable=False

[extras]
name=extras
mirrorlist=http://mirrorlist.centos.org/?release=8&arch=$basearch&repo=extras
failovermethod=priority
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Official
gpgcheck=1
skip_if_unavailable=False

[sclo]
name=sclo
baseurl=http://mirror.centos.org/centos/8/sclo/$basearch/sclo/
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-SIG-SCLo
gpgcheck=1
includepkgs=devtoolset*
skip_if_unavailable=False

[sclo-rh]
name=sclo-rh
mirrorlist=http://mirrorlist.centos.org/?release=8&arch=$basearch&repo=sclo-rh
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-SIG-SCLo
gpgcheck=1
includepkgs=devtoolset*
skip_if_unavailable=False

[testing]
name=epel-testing
enabled=0
mirrorlist=http://mirrors.fedoraproject.org/mirrorlist?repo=testing-epel8&arch=$basearch
failovermethod=priority
skip_if_unavailable=False

[local]
name=local
baseurl=https://kojipkgs.fedoraproject.org/repos/epel8-build/latest/$basearch/
cost=2000
enabled=0
skip_if_unavailable=False

[epel-debuginfo]
name=epel-debug
mirrorlist=http://mirrors.fedoraproject.org/mirrorlist?repo=epel-debug-8&arch=x86_64
failovermethod=priority
enabled=0
skip_if_unavailable=False
"""
