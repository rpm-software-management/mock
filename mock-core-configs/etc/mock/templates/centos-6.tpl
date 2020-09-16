# This list is taken from 'epel-6-x86_64' @buildsys-build group, minus the
# 'epel-*' specific stuff.
config_opts['chroot_setup_cmd'] = 'install bash bzip2 coreutils cpio diffutils findutils gawk gcc gcc-c++ grep gzip info make patch redhat-rpm-config rpm-build sed shadow-utils tar unzip util-linux-ng which xz'

config_opts['dist'] = 'el6'  # only useful for --resultdir variable subst
# beware RHEL uses 6Server or 6Client
config_opts['releasever'] = '6'
config_opts['isolation'] = 'simple'
config_opts['bootstrap_image'] = 'centos:6'
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
user_agent={{ user_agent }}

# repos
[base]
name=CentOS-$releasever - Base
enabled=1
mirrorlist=http://mirrorlist.centos.org/?release=6&arch=$basearch&repo=os
failovermethod=priority
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-6
gpgcheck=1
skip_if_unavailable=False

[updates]
name=CentOS-$releasever - Updates
enabled=1
mirrorlist=http://mirrorlist.centos.org/?release=6&arch=$basearch&repo=updates
failovermethod=priority
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-6
gpgcheck=1
skip_if_unavailable=False



{% if target_arch == "x86_64" %}
[centos-sclo-sclo]
name=CentOS-$releasever - SCLo sclo
baseurl=http://mirror.centos.org/centos/6/sclo/$basearch/sclo/
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-SIG-SCLo
gpgcheck=1
includepkgs=devtoolset*
skip_if_unavailable=False

[centos-sclo-rh]
name=CentOS-$releasever - SCLo rh
baseurl=http://mirror.centos.org/centos/6/sclo/$basearch/rh/
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-SIG-SCLo
gpgcheck=1
includepkgs=devtoolset*
skip_if_unavailable=False
{% endif %}
"""
