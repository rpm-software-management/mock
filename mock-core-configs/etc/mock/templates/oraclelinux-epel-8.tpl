config_opts['chroot_setup_cmd'] += " epel-rpm-macros"

config_opts['dnf.conf'] += """

# repos

[ol8_epel]
name=Oracle Linux 8 EPEL ($basearch)
baseurl=https://yum.oracle.com/repo/OracleLinux/OL8/developer/EPEL/$basearch
gpgkey=file:///usr/share/distribution-gpg-keys/oraclelinux/RPM-GPG-KEY-oracle-ol8
gpgcheck=1
enabled=1

"""
