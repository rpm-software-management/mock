config_opts['root'] = "rhelepel-8-{{ target_arch }}"

config_opts['yum.conf'] += """

[epel]
name="EPEL 8"
mirrorlist=http://mirrors.fedoraproject.org/mirrorlist?repo=epel-8&arch=$basearch
failovermethod=priority
gpgkey=file:///usr/share/distribution-gpg-keys/epel/RPM-GPG-KEY-EPEL-8
gpgcheck=1
skip_if_unavailable=False
"""
