config_opts['chroot_setup_cmd'] = 'install tar gcc-c++ redhat-rpm-config redhat-release oraclelinux-release which xz sed make bzip2 gzip gcc coreutils unzip shadow-utils diffutils cpio bash gawk rpm-build info patch util-linux findutils grep'
config_opts['dist'] = 'el8'  # only useful for --resultdir variable subst
config_opts['releasever'] = '8'
config_opts['package_manager'] = 'dnf'
config_opts['extra_chroot_dirs'] = [ '/run/lock', ]
config_opts['bootstrap_image'] = 'docker.io/library/oraclelinux:8'


config_opts['dnf.conf'] = """
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
install_weak_deps=0
protected_packages=
module_platform_id=platform:el8
user_agent={{ user_agent }}

# repos

[ol8_baseos_latest]
name=Oracle Linux 8 BaseOS Latest ($basearch)
baseurl=https://yum.oracle.com/repo/OracleLinux/OL8/baseos/latest/$basearch/
gpgkey=file:///usr/share/distribution-gpg-keys/oraclelinux/RPM-GPG-KEY-oracle-ol8
gpgcheck=1
enabled=1

[ol8_appstream]
name=Oracle Linux 8 Application Stream ($basearch)
baseurl=https://yum.oracle.com/repo/OracleLinux/OL8/appstream/$basearch/
gpgkey=file:///usr/share/distribution-gpg-keys/oraclelinux/RPM-GPG-KEY-oracle-ol8
gpgcheck=1
enabled=1

[ol8_codeready_builder]
name=Oracle Linux 8 CodeReady Builder ($basearch) - Unsupported
baseurl=https://yum.oracle.com/repo/OracleLinux/OL8/codeready/builder/$basearch/
gpgkey=file:///usr/share/distribution-gpg-keys/oraclelinux/RPM-GPG-KEY-oracle-ol8
gpgcheck=1
enabled=1

[ol8_distro_builder]
name=Oracle Linux 8 Distro Builder ($basearch) - Unsupported
baseurl=https://yum.oracle.com/repo/OracleLinux/OL8/distro/builder/$basearch/
gpgkey=file:///usr/share/distribution-gpg-keys/oraclelinux/RPM-GPG-KEY-oracle-ol8
gpgcheck=1
enabled=0

{% if target_arch in ['x86_64'] %}
[ol8_UEKR6]
name=Latest Unbreakable Enterprise Kernel Release 6 for Oracle Linux $releasever ($basearch)
baseurl=https://yum.oracle.com/repo/OracleLinux/OL8/UEKR6/$basearch/
gpgkey=file:///usr/share/distribution-gpg-keys/oraclelinux/RPM-GPG-KEY-oracle-ol8
gpgcheck=1
enabled=0
{% endif %}

"""
