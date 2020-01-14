config_opts['root'] = 'mageia-7-x86_64'
config_opts['target_arch'] = 'x86_64'
config_opts['legal_host_arches'] = ('x86_64',)
config_opts['chroot_setup_cmd'] = 'install basesystem-minimal rpm-build rpm-mageia-setup rpm-mageia-setup-build'
config_opts['dist'] = 'mga7'  # only useful for --resultdir variable subst
config_opts['extra_chroot_dirs'] = [ '/run/lock', ]
config_opts['useradd'] = '/usr/sbin/useradd -o -m -u %(uid)s -g %(gid)s -d %(home)s %(user)s'
config_opts['releasever'] = '7'
config_opts['macros']['%distro_section'] = 'core'
config_opts['package_manager'] = 'dnf'
config_opts['bootstrap_image'] = 'mageia:7'

config_opts['yum.conf'] = """
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

# repos

[mageia]
name=Mageia $releasever - x86_64
#baseurl=http://mirrors.kernel.org/mageia/distrib/$releasever/x86_64/media/core/release/
#metalink=https://mirrors.mageia.org/metalink?distrib=mageia-$releasever&arch=x86_64@&section=core&repo=release
mirrorlist=https://www.mageia.org/mirrorlist/?release=$releasever&arch=x86_64&section=core&repo=release
fastestmirror=1
gpgcheck=1
gpgkey=file:///usr/share/distribution-gpg-keys/mageia/RPM-GPG-KEY-Mageia
enabled=1
skip_if_unavailable=False

[updates]
name=Mageia $releasever - x86_64 - Updates
#baseurl=http://mirrors.kernel.org/mageia/distrib/$releasever/x86_64/media/core/updates/
#metalink=https://mirrors.mageia.org/metalink?distrib=mageia-$releasever&arch=x86_64@&section=core&repo=updates
mirrorlist=https://www.mageia.org/mirrorlist/?release=$releasever&arch=x86_64&section=core&repo=updates
fastestmirror=1
gpgcheck=1
gpgkey=file:///usr/share/distribution-gpg-keys/mageia/RPM-GPG-KEY-Mageia
enabled=1
skip_if_unavailable=False

[mageia-debuginfo]
name=Mageia $releasever - x86_64 - Debug
#baseurl=http://mirrors.kernel.org/mageia/distrib/$releasever/x86_64/media/debug/core/release/
#metalink=https://mirrors.mageia.org/metalink?distrib=mageia-$releasever&arch=x86_64@&section=core&repo=release&debug=true
mirrorlist=https://www.mageia.org/mirrorlist/?release=$releasever&arch=x86_64&section=core&repo=release&debug=1
fastestmirror=1
gpgcheck=1
gpgkey=file:///usr/share/distribution-gpg-keys/mageia/RPM-GPG-KEY-Mageia
enabled=0
skip_if_unavailable=False

[updates-debuginfo]
name=Mageia $releasever - x86_64 - Updates - Debug
#baseurl=http://mirrors.kernel.org/mageia/distrib/$releasever/x86_64/media/debug/core/updates/
#metalink=https://mirrors.mageia.org/metalink?distrib=mageia-$releasever&arch=x86_64@&section=core&repo=updates&debug=true
mirrorlist=https://www.mageia.org/mirrorlist/?release=$releasever&arch=x86_64&section=core&repo=updates&debug=1
fastestmirror=1
gpgcheck=1
gpgkey=file:///usr/share/distribution-gpg-keys/mageia/RPM-GPG-KEY-Mageia
enabled=0
skip_if_unavailable=False
"""
