config_opts['chroot_setup_cmd'] += " epel-rpm-macros"

config_opts['dnf.conf'] += """

# repos

[ol9_epel]
name=Oracle Linux 9 EPEL ($basearch)
baseurl=https://yum.oracle.com/repo/OracleLinux/OL9/developer/EPEL/$basearch
gpgkey=file:///usr/share/distribution-gpg-keys/oraclelinux/RPM-GPG-KEY-oracle-ol9
gpgcheck=1
enabled=1

"""
