config_opts['chroot_setup_cmd'] = 'install patterns-devel-base-devel_rpm_build'
config_opts['dist'] = 'suse.lp160'  # only useful for --resultdir variable subst
config_opts['extra_chroot_dirs'] = [ '/run/lock', ]
config_opts['releasever'] = '16.0'
config_opts['macros']['%dist'] = '.suse.lp160'
config_opts['package_manager'] = 'dnf'
config_opts['ssl_ca_bundle_path'] = '/var/lib/ca-certificates/ca-bundle.pem'
config_opts['description'] = 'openSUSE Leap {{ releasever }}'

# Container image contains zypper as the base package manager so it can't be used:
config_opts['use_bootstrap_image'] = False

# Due to the nature of the OpenSUSE mirroring system, we can not use
# metalinks easily and also we can not rely on the fact that baseurl's
# always work (issue #553) -- by design we need to expect a one minute
# repository problems (configured four attempts means 3 periods of 20s).
config_opts['package_manager_max_attempts'] = 4
config_opts['package_manager_attempt_delay'] = 20

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
install_weak_deps=0
metadata_expire=0
best=1

protected_packages=
user_agent={{ user_agent }}

# repos

[opensuse-leap-oss]
name=openSUSE Leap $releasever - {{ repo_arch }} - OSS
baseurl=https://download.opensuse.org/distribution/leap/$releasever/repo/oss/
#metalink=https://download.opensuse.org/distribution/leap/$releasever/repo/oss/repodata/repomd.xml.metalink
enabled=1
gpgkey=file:///usr/share/distribution-gpg-keys/opensuse/RPM-GPG-KEY-openSUSE-2022
       file:///usr/share/distribution-gpg-keys/suse/RPM-GPG-KEY-SuSE-ALP-Main
       file:///usr/share/distribution-gpg-keys/opensuse/RPM-GPG-KEY-openSUSE-16-Backports
gpgcheck=1

"""
