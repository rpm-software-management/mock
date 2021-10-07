config_opts['chroot_setup_cmd'] = 'install @buildsys-build'

config_opts['yum.conf'] += """

[ol7_epel]
name=Oracle Linux 7 EPEL ($basearch)
baseurl=https://yum.oracle.com/repo/OracleLinux/OL7/developer_EPEL/$basearch/
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-oracle
gpgcheck=1
enabled=1
"""
