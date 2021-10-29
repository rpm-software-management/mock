# EuroLinux open buildroots
# Note: perl modules are broken by design

config_opts['chroot_setup_cmd'] = 'install tar gcc-c++ redhat-rpm-config redhat-release which xz sed make bzip2 gzip gcc coreutils unzip shadow-utils diffutils cpio bash gawk rpm-build info patch util-linux findutils grep'
config_opts['dist'] = 'el8'  # only useful for --resultdir variable subst
config_opts['releasever'] = '8'
config_opts['package_manager'] = 'dnf'
config_opts['extra_chroot_dirs'] = [ '/run/lock', ]


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
module_platform_id=platform:el8


[baseos-all]
name=EuroLinux 8 BaseOS All
baseurl=https://fbi.cdn.euro-linux.com/dist/eurolinux/server/8/$basearch/certify-BaseOS/all/
gpgcheck=1
enabled=1
gpgkey=file:///usr/share/distribution-gpg-keys/eurolinux/RPM-GPG-KEY-eurolinux8

[appstream-all]
name=EuroLinux 8 AppStream All
baseurl=https://fbi.cdn.euro-linux.com/dist/eurolinux/server/8/$basearch/certify-AppStream/all/
gpgcheck=1
enabled=1
gpgkey=file:///usr/share/distribution-gpg-keys/eurolinux/RPM-GPG-KEY-eurolinux8

[powertools-all]
name=EuroLinux 8 PowerTools All
baseurl=https://fbi.cdn.euro-linux.com/dist/eurolinux/server/8/$basearch/certify-PowerTools/all/
gpgcheck=1
enabled=1
gpgkey=file:///usr/share/distribution-gpg-keys/eurolinux/RPM-GPG-KEY-eurolinux8

# There is no HA and RS for i686 or aarch64
{% if target_arch == 'x86_64' %}
[ha-all]
name=EuroLinux 8 HighAvailability All
baseurl=https://fbi.cdn.euro-linux.com/dist/eurolinux/server/8/$basearch/certify-HighAvailability/all/
gpgcheck=1
enabled=1
gpgkey=file:///usr/share/distribution-gpg-keys/eurolinux/RPM-GPG-KEY-eurolinux8

[rs-all]
name=EuroLinux 8 PowerTools All
baseurl=https://fbi.cdn.euro-linux.com/dist/eurolinux/server/8/$basearch/certify-ResilientStorage/all/
gpgcheck=1
enabled=1
gpgkey=file:///usr/share/distribution-gpg-keys/eurolinux/RPM-GPG-KEY-eurolinux8
{% endif %}
"""
