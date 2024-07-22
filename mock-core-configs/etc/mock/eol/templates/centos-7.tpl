# This list is taken from 'epel-7-x86_64' @buildsys-build group, minus the
# 'epel-*' specific stuff.
config_opts['chroot_setup_cmd'] = 'install bash bzip2 coreutils cpio diffutils findutils gawk gcc gcc-c++ grep gzip info make patch redhat-rpm-config rpm-build sed tar unzip util-linux which xz'

config_opts['dist'] = 'el7'  # only useful for --resultdir variable subst
config_opts['releasever'] = '7'
config_opts['bootstrap_image'] = 'quay.io/centos/centos:7'
config_opts['package_manager'] = 'yum'
config_opts['description'] = 'CentOS 7'

config_opts['yum_install_command'] += "{% if target_arch in ['x86_64', 'ppc64le', 'aarch64'] %} --disablerepo=centos-sclo*{% endif %}"

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

{% set centos_7_gpg_keys = 'file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-7' %}
{% if target_arch in ['ppc64le', 'ppc64'] %}
{%   set centos_7_gpg_keys = centos_7_gpg_keys + ',file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-SIG-AltArch-7-' + target_arch %}
{% elif target_arch in ['aarch64'] %}
{%   set centos_7_gpg_keys = centos_7_gpg_keys + ',file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-7-aarch64' %}
{% endif %}

# repos
[base]
name=CentOS-$releasever - Base
baseurl=https://vault.centos.org/7.9.2009/os/$basearch/
failovermethod=priority
gpgkey={{ centos_7_gpg_keys }}
gpgcheck=1
skip_if_unavailable=False

[updates]
name=CentOS-$releasever - Updates
enabled=1
baseurl=https://vault.centos.org/7.9.2009/updates/$basearch/
failovermethod=priority
gpgkey={{ centos_7_gpg_keys }}
gpgcheck=1
skip_if_unavailable=False

[extras]
name=CentOS-$releasever - Extras
baseurl=https://vault.centos.org/7.9.2009/extras/$basearch/
failovermethod=priority
gpgkey={{ centos_7_gpg_keys }}
gpgcheck=1
skip_if_unavailable=False

[fastrack]
name=CentOS-$releasever - fasttrack
baseurl=https://vault.centos.org/7.9.2009/fasttrack/$basearch/
failovermethod=priority
gpgkey={{ centos_7_gpg_keys }}
gpgcheck=1
skip_if_unavailable=False
enabled=0

[centosplus]
name=CentOS-$releasever - Plus
baseurl=https://vault.centos.org/7.9.2009/centosplus/$basearch/
gpgkey={{ centos_7_gpg_keys }}
gpgcheck=1
enabled=0

{% if target_arch == 'x86_64' %}
[centos-sclo-sclo]
name=CentOS-$releasever - SCLo sclo
baseurl=https://vault.centos.org/7.9.2009/sclo/$basearch/sclo/
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-SIG-SCLo
gpgcheck=1
skip_if_unavailable=False
{% endif %}

{% if target_arch in ['x86_64', 'ppc64le', 'aarch64'] %}
[centos-sclo-rh]
name=CentOS-$releasever - SCLo rh
baseurl=https://vault.centos.org/7.9.2009/sclo/$basearch/rh/
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-SIG-SCLo
gpgcheck=1
skip_if_unavailable=False
{% endif %}
"""
