# EuroLinux open buildroots

config_opts['chroot_setup_cmd'] = 'install tar gcc-c++ redhat-rpm-config redhat-release which xz sed make bzip2 gzip gcc coreutils unzip diffutils cpio bash gawk rpm-build info patch util-linux findutils grep'
config_opts['dist'] = 'el9'  # only useful for --resultdir variable subst
config_opts['releasever'] = '9'
config_opts['package_manager'] = 'dnf'
config_opts['extra_chroot_dirs'] = [ '/run/lock', ]
config_opts['description'] = 'EuroLinux 9'
config_opts['bootstrap_image'] = 'docker.io/eurolinux/eurolinux-9'

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
best=0
protected_packages=
module_platform_id=platform:el9


[baseos-all]
name=EuroLinux 9 BaseOS All
baseurl=https://fbi.cdn.euro-linux.com/dist/eurolinux/server/9/$basearch/BaseOS/all/
gpgcheck=1
enabled=1
gpgkey=file:///usr/share/distribution-gpg-keys/eurolinux/RPM-GPG-KEY-eurolinux9

[appstream-all]
name=EuroLinux 9 AppStream All
baseurl=https://fbi.cdn.euro-linux.com/dist/eurolinux/server/9/$basearch/AppStream/all/
gpgcheck=1
enabled=1
gpgkey=file:///usr/share/distribution-gpg-keys/eurolinux/RPM-GPG-KEY-eurolinux9

[crb-all]
name=EuroLinux 9 CodeReady Linux Builder All
baseurl=https://fbi.cdn.euro-linux.com/dist/eurolinux/server/9/$basearch/CRB/all/
gpgcheck=1
enabled=1
gpgkey=file:///usr/share/distribution-gpg-keys/eurolinux/RPM-GPG-KEY-eurolinux9

# There is no HA and RS for i686 or aarch64
{% if target_arch == 'x86_64' %}
[ha-all]
name=EuroLinux 9 HighAvailability All
baseurl=https://fbi.cdn.euro-linux.com/dist/eurolinux/server/9/$basearch/HighAvailability/all/
gpgcheck=1
enabled=1
gpgkey=file:///usr/share/distribution-gpg-keys/eurolinux/RPM-GPG-KEY-eurolinux9

[rs-all]
name=EuroLinux 9 PowerTools All
baseurl=https://fbi.cdn.euro-linux.com/dist/eurolinux/server/9/$basearch/ResilientStorage/all/
gpgcheck=1
enabled=1
gpgkey=file:///usr/share/distribution-gpg-keys/eurolinux/RPM-GPG-KEY-eurolinux9
{% endif %}
"""
