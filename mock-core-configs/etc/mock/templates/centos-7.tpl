# This list is taken from 'epel-7-x86_64' @buildsys-build group, minus the
# 'epel-*' specific stuff.
config_opts['chroot_setup_cmd'] = 'install bash bzip2 coreutils cpio diffutils findutils gawk gcc gcc-c++ grep gzip info make patch redhat-rpm-config rpm-build sed shadow-utils tar unzip util-linux which xz'
config_opts['chroot_additional_packages'] = 'scl-utils-build'

config_opts['dist'] = 'el7'  # only useful for --resultdir variable subst
config_opts['releasever'] = '7'
config_opts['bootstrap_image'] = 'quay.io/centos/centos:7'
config_opts['package_manager'] = 'yum'
config_opts['yum_vars'] = { 'contentdir': "{% if target_arch in ['x86_64'] -%} centos {%- else -%} altarch {%- endif %}",
                            'infra': 'stock',
                          }

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

{% set centos_7_arch_gpg_key -%}
{% if target_arch in ['ppc64le', 'ppc64'] %}
       file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-SIG-AltArch-7-{{ target_arch }}
{%- elif target_arch == 'aarch64' %}
       file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-7-aarch64
{%- endif -%}
{% endset -%}

# repos
[base]
name=CentOS-$releasever - Base
mirrorlist=http://mirrorlist.centos.org/?release=$releasever&arch=$basearch&repo=os&infra=$infra
#baseurl=http://mirror.centos.org/$contentdir/$releasever/os/$basearch/
failovermethod=priority
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-7
       {{- centos_7_arch_gpg_key }}
gpgcheck=1
skip_if_unavailable=False

[updates]
name=CentOS-$releasever - Updates
mirrorlist=http://mirrorlist.centos.org/?release=$releasever&arch=$basearch&repo=updates&infra=$infra
#baseurl=http://mirror.centos.org/$contentdir/$releasever/updates/$basearch/
failovermethod=priority
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-7
       {{- centos_7_arch_gpg_key }}
gpgcheck=1
skip_if_unavailable=False

[extras]
name=CentOS-$releasever - Extras
mirrorlist=http://mirrorlist.centos.org/?release=$releasever&arch=$basearch&repo=extras&infra=$infra
#baseurl=http://mirror.centos.org/$contentdir/$releasever/extras/$basearch/
failovermethod=priority
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-7
       {{- centos_7_arch_gpg_key }}
gpgcheck=1
skip_if_unavailable=False

[fasttrack]
name=CentOS-$releasever - fasttrack
mirrorlist=http://mirrorlist.centos.org/?release=$releasever&arch=$basearch&repo=fasttrack&infra=$infra
#baseurl=http://mirror.centos.org/$contentdir/$releasever/fasttrack/$basearch/
failovermethod=priority
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-7
       {{- centos_7_arch_gpg_key }}
gpgcheck=1
skip_if_unavailable=False
enabled=0

[centosplus]
name=CentOS-$releasever - Plus
mirrorlist=http://mirrorlist.centos.org/?release=$releasever&arch=$basearch&repo=centosplus&infra=$infra
#baseurl=http://mirror.centos.org/$contentdir/$releasever/centosplus/$basearch/
failovermethod=priority
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-7
       {{- centos_7_arch_gpg_key }}
gpgcheck=1
skip_if_unavailable=False
enabled=0

[cr]
name=CentOS-$releasever - cr
baseurl=http://mirror.centos.org/$contentdir/$releasever/cr/$basearch/
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-7
       {{- centos_7_arch_gpg_key }}
gpgcheck=1
skip_if_unavailable=False
enabled=0

[base-debuginfo]
name=CentOS-$releasever - Debuginfo
baseurl=http://debuginfo.centos.org/$releasever/$basearch/
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-Debug-7
gpgcheck=1
skip_if_unavailable=False
enabled=0

[base-source]
name=CentOS-$releasever - Base Sources
baseurl=http://vault.centos.org/centos/$releasever/os/Source/
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-7
gpgcheck=1
skip_if_unavailable=False
enabled=0

[updates-source]
name=CentOS-$releasever - Updates Sources
baseurl=http://vault.centos.org/centos/$releasever/updates/Source/
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-7
gpgcheck=1
skip_if_unavailable=False
enabled=0

[extras-source]
name=CentOS-$releasever - Extras Sources
baseurl=http://vault.centos.org/centos/$releasever/extras/Source/
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-7
gpgcheck=1
skip_if_unavailable=False
enabled=0

[centosplus-source]
name=CentOS-$releasever - Plus Sources
baseurl=http://vault.centos.org/centos/$releasever/centosplus/Source/
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-7
gpgcheck=1
skip_if_unavailable=False
enabled=0

{% if target_arch in ['x86_64', 'ppc64le', 'aarch64'] %}
[centos-sclo-sclo]
name=CentOS-$releasever - SCLo sclo
mirrorlist=http://mirrorlist.centos.org/?release=$releasever&arch=$basearch&repo=sclo-sclo&infra=$infra
#baseurl=http://mirror.centos.org/$contentdir/$releasever/sclo/$basearch/sclo/
failovermethod=priority
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-SIG-SCLo
gpgcheck=1
skip_if_unavailable=False

[centos-sclo-rh]
name=CentOS-$releasever - SCLo rh
mirrorlist=http://mirrorlist.centos.org/?release=$releasever&arch=$basearch&repo=sclo-rh&infra=$infra
#baseurl=http://mirror.centos.org/$contentdir/$releasever/sclo/$basearch/rh/
failovermethod=priority
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-SIG-SCLo
gpgcheck=1
skip_if_unavailable=False
{% endif %}
"""
