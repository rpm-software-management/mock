config_opts['chroot_setup_cmd'] = 'install tar gcc-c++ kylin-rpm-config kylin-release which xz sed make bzip2 gzip gcc coreutils unzip diffutils cpio bash gawk rpm-build info patch util-linux findutils grep'
config_opts['dist'] = 'ky10' # only useful for --resultdir variable subst
config_opts['releasever'] = '10'
config_opts['package_manager'] = 'dnf'
config_opts['extra_chroot_dirs'] = [ '/run/lock', ]

# No official image available:
config_opts['use_bootstrap_image'] = False

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
module_platform_id=platform:ky10
user_agent={{ user_agent }}

[ks10-adv-os]
name = Kylin Linux Advanced Server V10 - OS
baseurl = https://update.cs2c.com.cn/NS/V10/V10SP3-2403/os/adv/lic/base/$basearch/
gpgkey = file:///usr/share/distribution-gpg-keys/kylin/RPM-GPG-KEY-kylin
gpgcheck = 1
enabled = 1

[ks10-adv-updates]
name = Kylin Linux Advanced Server V10 - Updates
baseurl = https://update.cs2c.com.cn/NS/V10/V10SP3-2403/os/adv/lic/updates/$basearch/
gpgkey = file:///usr/share/distribution-gpg-keys/kylin/RPM-GPG-KEY-kylin
gpgcheck = 1
enabled = 1
# This repository is not present if a minor release is out but without any update yet:
skip_if_unavailable = 1

"""
