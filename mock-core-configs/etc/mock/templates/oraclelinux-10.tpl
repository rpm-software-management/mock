config_opts['chroot_setup_cmd'] = 'install tar redhat-rpm-config redhat-release oraclelinux-release which xz sed make bzip2 gzip coreutils unzip diffutils cpio bash gawk rpm-build info patch util-linux findutils grep glibc-minimal-langpack'
config_opts['dist'] = 'el10'  # only useful for --resultdir variable subst
config_opts['releasever'] = '10'
config_opts['package_manager'] = 'dnf'
config_opts['extra_chroot_dirs'] = [ '/run/lock', ]
config_opts['bootstrap_image'] = 'container-registry.oracle.com/os/oraclelinux:10'
config_opts['description'] = 'Oracle Linux 10'

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
module_platform_id=platform:el10
user_agent={{ user_agent }}

# repos

[ol10_baseos_latest]
name=Oracle Linux 10 BaseOS Latest ($basearch)
baseurl=https://yum.oracle.com/repo/OracleLinux/OL10/baseos/latest/$basearch/
gpgkey=file:///usr/share/distribution-gpg-keys/oraclelinux/RPM-GPG-KEY-oracle-ol10
gpgcheck=1
enabled=1

[ol10_appstream]
name=Oracle Linux 10 Application Stream ($basearch)
baseurl=https://yum.oracle.com/repo/OracleLinux/OL10/appstream/$basearch/
gpgkey=file:///usr/share/distribution-gpg-keys/oraclelinux/RPM-GPG-KEY-oracle-ol10
gpgcheck=1
enabled=1

[ol10_codeready_builder]
name=Oracle Linux 10 CodeReady Builder ($basearch) - Unsupported
baseurl=https://yum.oracle.com/repo/OracleLinux/OL10/codeready/builder/$basearch/
gpgkey=file:///usr/share/distribution-gpg-keys/oraclelinux/RPM-GPG-KEY-oracle-ol10
gpgcheck=1
enabled=1

[ol10_distro_builder]
name=Oracle Linux 10 Distro Builder ($basearch) - Unsupported
baseurl=https://yum.oracle.com/repo/OracleLinux/OL10/distro/builder/$basearch/
gpgkey=file:///usr/share/distribution-gpg-keys/oraclelinux/RPM-GPG-KEY-oracle-ol10
gpgcheck=1
enabled=0

{% if target_arch in ['x86_64'] %}
[ol10_UEKR7]
name=Latest Unbreakable Enterprise Kernel Release 7 for Oracle Linux $releasever ($basearch)
baseurl=https://yum.oracle.com/repo/OracleLinux/OL10/UEKR7/$basearch/
gpgkey=file:///usr/share/distribution-gpg-keys/oraclelinux/RPM-GPG-KEY-oracle-ol10
gpgcheck=1
enabled=0
{% endif %}

"""
