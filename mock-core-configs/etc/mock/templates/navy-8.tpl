config_opts['chroot_setup_cmd'] = 'install tar gcc-c++ redhat-rpm-config system-release which xz sed make bzip2 gzip gcc coreutils unzip shadow-utils diffutils cpio bash gawk rpm-build info patch util-linux findutils grep'
config_opts['dist'] = 'el8'  # only useful for --resultdir variable subst
config_opts['releasever'] = '8'
config_opts['package_manager'] = 'yum'
config_opts['extra_chroot_dirs'] = [ '/run/lock', ]
config_opts['macros']['%dist'] = '.el8'
config_opts['bootstrap_image'] = 'navylinux:8'
config_opts['macros']['vendor'] = "The Navy Linux Project."
config_opts['macros']['packager'] = "packager@navylinux.org"
config_opts['macros']['%releasever'] = "8"


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
mdpolicy=group:primary
best=1
protected_packages=
module_platform_id=platform:el8
user_agent={{ user_agent }}

[nl-base]
name=Navy Linux Enterprise OS Repository - el$releasever
baseurl=https://cdn.navylinux.org/navylinux/releases/8.4r1/x86_64/os/
enabled=1
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-navy-linux-official

[nl-every]
name=Navy Linux Enterprise Every Repository - el$releasever
baseurl=https://cdn.navylinux.org/navylinux/releases/8.4r1/x86_64/everything/
enabled=1
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-navy-linux-official

[nl-powertools]
name=Navy Linux Enterprise Power Repository - el$releasever
baseurl=https://cdn.navylinux.org/navylinux/releases/8.4r1/x86_64/powertools/
enabled=1
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-navy-linux-official

[nl-kernel]
name=Navy Linux Enterprise Kernel  Repository - el$releasever
baseurl=https://cdn.navylinux.org/navylinux/releases/8.4r1/x86_64/kernel/
enabled=1
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-navy-linux-official

[epel]
name=Extra Packages for Enterprise Linux $releasever 
baseurl=https://dl.fedoraproject.org/pub/epel/8/Everything/x86_64/
failovermethod=priority
gpgkey=file:///usr/share/distribution-gpg-keys/epel/RPM-GPG-KEY-EPEL-8
gpgcheck=1
skip_if_unavailable=False


"""

