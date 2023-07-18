config_opts['chroot_setup_cmd'] = 'install tar redhat-rpm-config redhat-release oraclelinux-release which xz sed make bzip2 gzip coreutils unzip diffutils cpio bash gawk rpm-build info patch util-linux findutils grep glibc-minimal-langpack'
config_opts['dist'] = 'el9'  # only useful for --resultdir variable subst
config_opts['releasever'] = '9'
config_opts['package_manager'] = 'dnf'
config_opts['extra_chroot_dirs'] = [ '/run/lock', ]
config_opts['bootstrap_image'] = 'container-registry.oracle.com/os/oraclelinux:9'
config_opts['description'] = 'Oracle Linux 9'

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
module_platform_id=platform:el9
user_agent={{ user_agent }}

# repos

[ol9_baseos_latest]
name=Oracle Linux 9 BaseOS Latest ($basearch)
baseurl=https://yum.oracle.com/repo/OracleLinux/OL9/baseos/latest/$basearch/
gpgkey=file:///usr/share/distribution-gpg-keys/oraclelinux/RPM-GPG-KEY-oracle-ol9
gpgcheck=1
enabled=1

[ol9_appstream]
name=Oracle Linux 9 Application Stream ($basearch)
baseurl=https://yum.oracle.com/repo/OracleLinux/OL9/appstream/$basearch/
gpgkey=file:///usr/share/distribution-gpg-keys/oraclelinux/RPM-GPG-KEY-oracle-ol9
gpgcheck=1
enabled=1

[ol9_codeready_builder]
name=Oracle Linux 9 CodeReady Builder ($basearch) - Unsupported
baseurl=https://yum.oracle.com/repo/OracleLinux/OL9/codeready/builder/$basearch/
gpgkey=file:///usr/share/distribution-gpg-keys/oraclelinux/RPM-GPG-KEY-oracle-ol9
gpgcheck=1
enabled=1

[ol9_distro_builder]
name=Oracle Linux 9 Distro Builder ($basearch) - Unsupported
baseurl=https://yum.oracle.com/repo/OracleLinux/OL9/distro/builder/$basearch/
gpgkey=file:///usr/share/distribution-gpg-keys/oraclelinux/RPM-GPG-KEY-oracle-ol9
gpgcheck=1
enabled=0

{% if target_arch in ['x86_64'] %}
[ol9_UEKR7]
name=Latest Unbreakable Enterprise Kernel Release 7 for Oracle Linux $releasever ($basearch)
baseurl=https://yum.oracle.com/repo/OracleLinux/OL9/UEKR7/$basearch/
gpgkey=file:///usr/share/distribution-gpg-keys/oraclelinux/RPM-GPG-KEY-oracle-ol9
gpgcheck=1
enabled=0
{% endif %}

"""
