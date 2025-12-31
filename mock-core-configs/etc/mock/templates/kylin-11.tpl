config_opts['chroot_setup_cmd'] = 'install tar gcc-c++ kylin-rpm-config kylin-release which xz sed make bzip2 gzip gcc coreutils unzip diffutils cpio bash gawk rpm-build info patch util-linux findutils grep'
config_opts['dist'] = 'ky11' # only useful for --resultdir variable subst
config_opts['releasever'] = '11'
config_opts['package_manager'] = 'dnf'
config_opts['extra_chroot_dirs'] = [ '/run/lock', ]

# Registry web interface: https://cr.kylinos.cn/zh/image
config_opts['bootstrap_image'] = 'cr.kylinos.cn/kylin/kylin-server-platform:v11-2503'

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
module_platform_id=platform:ky11
user_agent={{ user_agent }}

[ks11-adv-os]
name = Kylin Linux Advanced Server V11 - OS
baseurl = https://update.cs2c.com.cn/NS/V11/2503/os/adv/lic/base/$basearch/
gpgkey = file:///usr/share/distribution-gpg-keys/kylin/RPM-GPG-KEY-kylin
gpgcheck = 1
enabled = 1

[ks11-adv-updates]
name = Kylin Linux Advanced Server V11 - Updates
baseurl = https://update.cs2c.com.cn/NS/V11/2503/os/adv/lic/updates/$basearch/
gpgkey = file:///usr/share/distribution-gpg-keys/kylin/RPM-GPG-KEY-kylin
gpgcheck = 1
enabled = 1
# This repository is not present if a minor release is out but without any update yet:
skip_if_unavailable = 1

"""
