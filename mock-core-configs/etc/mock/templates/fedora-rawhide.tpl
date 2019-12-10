config_opts['root'] = 'fedora-rawhide-{{ target_arch }}'
# config_opts['module_enable'] = ['list', 'of', 'modules']
# config_opts['module_install'] = ['module1/profile', 'module2/profile']
config_opts['chroot_setup_cmd'] = 'install @buildsys-build'
config_opts['dist'] = 'rawhide'  # only useful for --resultdir variable subst
config_opts['extra_chroot_dirs'] = [ '/run/lock', ]
config_opts['releasever'] = '32'

config_opts['package_manager'] = 'dnf'

config_opts['bootstrap_image'] = 'fedora:rawhide'


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
module_platform_id=platform:f32
protected_packages=

# repos

[local]
name=local
baseurl=https://kojipkgs.fedoraproject.org/repos/rawhide/latest/$basearch/
cost=2000
enabled=0
skip_if_unavailable=False

[local-source]
name=local-source
baseurl=https://kojipkgs.fedoraproject.org/repos/rawhide/latest/src/
cost=2000
enabled=0
skip_if_unavailable=False

[fedora]
name=fedora
metalink=https://mirrors.fedoraproject.org/metalink?repo=rawhide&arch=$basearch
gpgkey=file:///usr/share/distribution-gpg-keys/fedora/RPM-GPG-KEY-fedora-$releasever-primary file:///usr/share/distribution-gpg-keys/fedora/RPM-GPG-KEY-fedora-32-primary file:///usr/share/distribution-gpg-keys/fedora/RPM-GPG-KEY-fedora-31-primary
gpgcheck=1
skip_if_unavailable=False

[fedora-debuginfo]
name=Fedora Rawhide - Debug
metalink=https://mirrors.fedoraproject.org/metalink?repo=rawhide-debug&arch=$basearch
enabled=0
gpgkey=file:///usr/share/distribution-gpg-keys/fedora/RPM-GPG-KEY-fedora-$releasever-primary file:///usr/share/distribution-gpg-keys/fedora/RPM-GPG-KEY-fedora-32-primary file:///usr/share/distribution-gpg-keys/fedora/RPM-GPG-KEY-fedora-31-primary
gpgcheck=1
skip_if_unavailable=False

[fedora-source]
name=fedora-source
metalink=https://mirrors.fedoraproject.org/metalink?repo=rawhide-source&arch=$basearch
gpgkey=file:///usr/share/distribution-gpg-keys/fedora/RPM-GPG-KEY-fedora-$releasever-primary file:///usr/share/distribution-gpg-keys/fedora/RPM-GPG-KEY-fedora-32-primary file:///usr/share/distribution-gpg-keys/fedora/RPM-GPG-KEY-fedora-31-primary
gpgcheck=1
enabled=0
skip_if_unavailable=False

# modular

[rawhide-modular]
name=Fedora - Modular Rawhide - Developmental packages for the next Fedora release
metalink=https://mirrors.fedoraproject.org/metalink?repo=rawhide-modular&arch=$basearch
# if you want to enable it, you should set best=0
# see https://bugzilla.redhat.com/show_bug.cgi?id=1673851
enabled=0
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-fedora-$releasever-$basearch file:///usr/share/distribution-gpg-keys/fedora/RPM-GPG-KEY-fedora-32-primary file:///usr/share/distribution-gpg-keys/fedora/RPM-GPG-KEY-fedora-31-primary
skip_if_unavailable=False

[rawhide-modular-debuginfo]
name=Fedora - Modular Rawhide - Debug
metalink=https://mirrors.fedoraproject.org/metalink?repo=rawhide-modular-debug&arch=$basearch
enabled=0
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-fedora-$releasever-$basearch file:///usr/share/distribution-gpg-keys/fedora/RPM-GPG-KEY-fedora-32-primary file:///usr/share/distribution-gpg-keys/fedora/RPM-GPG-KEY-fedora-31-primary
skip_if_unavailable=False

[rawhide-modular-source]
name=Fedora - Modular Rawhide - Source
metalink=https://mirrors.fedoraproject.org/metalink?repo=rawhide-modular-source&arch=$basearch
enabled=0
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-fedora-$releasever-$basearch file:///usr/share/distribution-gpg-keys/fedora/RPM-GPG-KEY-fedora-32-primary file:///usr/share/distribution-gpg-keys/fedora/RPM-GPG-KEY-fedora-31-primary
skip_if_unavailable=False
"""
