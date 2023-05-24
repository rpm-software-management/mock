config_opts['chroot_setup_cmd'] = 'install tar gcc-c++ openEuler-rpm-config openEuler-release which xz sed make bzip2 gzip gcc coreutils unzip shadow-utils diffutils cpio bash gawk rpm-build info patch util-linux findutils grep'
config_opts['dist'] = 'oe2003'  # only useful for --resultdir variable subst
config_opts['releasever'] = '20.03-LTS'
config_opts['package_manager'] = 'dnf'
config_opts['description'] = 'openEuler 20.03 LTS'
config_opts['extra_chroot_dirs'] = [ '/run/lock', ]
config_opts['bootstrap_image'] = 'docker.io/openeuler/openeuler:20.03-lts'

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
module_platform_id=platform:oe2003
user_agent={{ user_agent }}

[OS]
name=OS
metalink=https://mirrors.openeuler.org/metalink?repo=openEuler-20.03-LTS-SP3/OS&arch=$basearch
enabled=1
gpgcheck=1
gpgkey=file:///usr/share/distribution-gpg-keys/openeuler/RPM-GPG-KEY-openEuler

[everything]
name=everything
metalink=https://mirrors.openeuler.org/metalink?repo=openEuler-20.03-LTS-SP3/everything&arch=$basearch
enabled=1
gpgcheck=1
gpgkey=file:///usr/share/distribution-gpg-keys/openeuler/RPM-GPG-KEY-openEuler

[EPOL]
name=EPOL
metalink=https://mirrors.openeuler.org/metalink?repo=openEuler-20.03-LTS-SP3/EPOL/main&arch=$basearch
enabled=1
gpgcheck=1
gpgkey=file:///usr/share/distribution-gpg-keys/openeuler/RPM-GPG-KEY-openEuler

[debuginfo]
name=debuginfo
metalink=https://mirrors.openeuler.org/metalink?repo=openEuler-20.03-LTS-SP3/debuginfo&arch=$basearch
enabled=0
gpgcheck=1
gpgkey=file:///usr/share/distribution-gpg-keys/openeuler/RPM-GPG-KEY-openEuler

[source]
name=source
metalink=https://mirrors.openeuler.org/metalink?path=openeuler/openEuler-20.03-LTS-SP3/source/repodata/repomd.xml
enabled=0
gpgcheck=1
gpgkey=file:///usr/share/distribution-gpg-keys/openeuler/RPM-GPG-KEY-openEuler

[update]
name=update
metalink=https://mirrors.openeuler.org/metalink?repo=openEuler-20.03-LTS-SP3/update&arch=$basearch
enabled=1
gpgcheck=1
gpgkey=file:///usr/share/distribution-gpg-keys/openeuler/RPM-GPG-KEY-openEuler
"""
