config_opts['root'] = 'amazonlinux-2023-{{ target_arch }}'
config_opts['chroot_setup_cmd'] = 'install system-release bash bzip2 coreutils cpio diffutils findutils gawk glibc-minimal-langpack grep gzip info patch rpm-build sed shadow-utils system-rpm-config tar unzip util-linux which xz'
config_opts['dist'] = 'amzn2023' # only useful for --resultdir variable subst
config_opts['plugin_conf']['ccache_enable'] = False
config_opts['package_manager'] = 'dnf'
config_opts['description'] = 'Amazon Linux 2023'
config_opts['releasever'] = '2023'

config_opts['bootstrap_image'] = 'public.ecr.aws/amazonlinux/amazonlinux:2023'

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
sysleg_device=
install_weak_deps=0
user_agent={{ user_agent }}

[amazonlinux]
name=Amazon Linux $releasever repository - $basearch
mirrorlist=https://cdn.amazonlinux.com/al${releasever}/core/mirrors/latest/$basearch/mirror.list
enabled=1
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey=file:///usr/share/distribution-gpg-keys/amazon-linux/RPM-GPG-KEY-amazon-linux-$releasever

[amazonlinux-source]
name=Amazon Linux $releasever repository - Source packages
mirrorlist=https://cdn.amazonlinux.com/al${releasever}/core/mirrors/latest/SRPMS/mirror.list
enabled=0
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey=file:///usr/share/distribution-gpg-keys/amazon-linux/RPM-GPG-KEY-amazon-linux-$releasever

[amazonlinux-debuginfo]
name=Amazon Linux $releasever repository - $basearch - Debug
mirrorlist=https://cdn.amazonlinux.com/al${releasever}/core/mirrors/latest/debuginfo/$basearch/mirror.list
enabled=0
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey=file:///usr/share/distribution-gpg-keys/amazon-linux/RPM-GPG-KEY-amazon-linux-$releasever
"""
