config_opts['root'] = 'epel-7-x86_64'
config_opts['target_arch'] = 'x86_64'
config_opts['legal_host_arches'] = ('x86_64',)
config_opts['chroot_setup_cmd'] = 'install @buildsys-build'
config_opts['dist'] = 'el7'  # only useful for --resultdir variable subst
config_opts['releasever'] = '7'
config_opts['yum_install_command'] += ' --disablerepo=sclo*'
config_opts['bootstrap_image'] = 'centos:7'
config_opts['package_manager'] = 'yum'

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

# repos
[base]
name=BaseOS
mirrorlist=http://mirrorlist.centos.org/?release=7&arch=x86_64&repo=os
failovermethod=priority
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-7
gpgcheck=1
skip_if_unavailable=False

[updates]
name=updates
enabled=1
mirrorlist=http://mirrorlist.centos.org/?release=7&arch=x86_64&repo=updates
failovermethod=priority
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-7
gpgcheck=1
skip_if_unavailable=False

[epel]
name=epel
mirrorlist=http://mirrors.fedoraproject.org/mirrorlist?repo=epel-7&arch=x86_64
failovermethod=priority
gpgkey=file:///usr/share/distribution-gpg-keys/epel/RPM-GPG-KEY-EPEL-7
gpgcheck=1
skip_if_unavailable=False

[extras]
name=extras
mirrorlist=http://mirrorlist.centos.org/?release=7&arch=x86_64&repo=extras
failovermethod=priority
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-7
gpgcheck=1
skip_if_unavailable=False

[sclo]
name=sclo
baseurl=http://mirror.centos.org/centos/7/sclo/x86_64/sclo/
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-SIG-SCLo
gpgcheck=1
includepkgs=devtoolset*
skip_if_unavailable=False

[sclo-rh]
name=sclo-rh
mirrorlist=http://mirrorlist.centos.org/?release=7&arch=x86_64&repo=sclo-rh
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-SIG-SCLo
gpgcheck=1
includepkgs=devtoolset*
skip_if_unavailable=False

[testing]
name=epel-testing
enabled=0
mirrorlist=http://mirrors.fedoraproject.org/mirrorlist?repo=testing-epel7&arch=x86_64
failovermethod=priority
skip_if_unavailable=False

[local]
name=local
baseurl=https://kojipkgs.fedoraproject.org/repos/epel7-build/latest/x86_64/
cost=2000
enabled=0
skip_if_unavailable=False

[epel-debuginfo]
name=epel-debug
mirrorlist=http://mirrors.fedoraproject.org/mirrorlist?repo=epel-debug-7&arch=x86_64
failovermethod=priority
enabled=0
skip_if_unavailable=False
"""
