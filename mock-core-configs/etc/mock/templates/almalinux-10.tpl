config_opts['chroot_setup_cmd'] = 'install bash bzip2 coreutils cpio diffutils redhat-release findutils gawk glibc-minimal-langpack grep gzip info patch redhat-rpm-config rpm-build sed tar unzip util-linux which xz'
config_opts['dist'] = 'el10.alma'  # only useful for --resultdir variable subst
config_opts['releasever'] = '10'
config_opts['releasever_major'] = '10'
config_opts['package_manager'] = 'dnf'
config_opts['extra_chroot_dirs'] = [ '/run/lock', ]
config_opts['bootstrap_image'] = 'quay.io/almalinuxorg/almalinux:10'

# deal with special handling for x86_64_v2 variant
config_opts['mirrorlist_arch'] = "{% if repo_arch == 'x86_64_v2' %}?arch=x86_64_v2{% endif %}"
config_opts['baseurl_arch'] = "{% if repo_arch == 'x86_64_v2' %}x86_64_v2{% else %}$basearch{% endif %}"
config_opts['use_bootstrap_image'] = "{% if repo_arch == 'x86_64_v2' %}False{% else %}True{% endif %}"

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
module_platform_id=platform:el10
user_agent={{ user_agent }}


[baseos]
name=AlmaLinux $releasever - BaseOS
mirrorlist=https://mirrors.almalinux.org/mirrorlist/$releasever/baseos{{ mirrorlist_arch }}
# baseurl=https://repo.almalinux.org/almalinux/$releasever/BaseOS/{{ baseurl_arch }}/os/
enabled=1
gpgcheck=1
countme=1
gpgkey=file:///usr/share/distribution-gpg-keys/alma/RPM-GPG-KEY-AlmaLinux-10

[baseos-debuginfo]
name=AlmaLinux $releasever - BaseOS - Debug
mirrorlist=https://mirrors.almalinux.org/mirrorlist/$releasever/baseos-debug{{ mirrorlist_arch }}
# baseurl=https://vault.almalinux.org/$releasever/BaseOS/debug/{{ baseurl_arch }}/
enabled=0
gpgcheck=1
gpgkey=file:///usr/share/distribution-gpg-keys/alma/RPM-GPG-KEY-AlmaLinux-10

[baseos-source]
name=AlmaLinux $releasever - BaseOS - Source
mirrorlist=https://mirrors.almalinux.org/mirrorlist/$releasever/baseos-source
# baseurl=https://vault.almalinux.org/$releasever/BaseOS/Source/
enabled=0
gpgcheck=1
gpgkey=file:///usr/share/distribution-gpg-keys/alma/RPM-GPG-KEY-AlmaLinux-10


[appstream]
name=AlmaLinux $releasever - AppStream
mirrorlist=https://mirrors.almalinux.org/mirrorlist/$releasever/appstream{{ mirrorlist_arch }}
# baseurl=https://repo.almalinux.org/almalinux/$releasever/AppStream/{{ baseurl_arch }}/os/
enabled=1
gpgcheck=1
countme=1
gpgkey=file:///usr/share/distribution-gpg-keys/alma/RPM-GPG-KEY-AlmaLinux-10

[appstream-debuginfo]
name=AlmaLinux $releasever - AppStream - Debug
mirrorlist=https://mirrors.almalinux.org/mirrorlist/$releasever/appstream-debug{{ mirrorlist_arch }}
# baseurl=https://vault.almalinux.org/$releasever/AppStream/debug/{{ baseurl_arch }}/
enabled=0
gpgcheck=1
gpgkey=file:///usr/share/distribution-gpg-keys/alma/RPM-GPG-KEY-AlmaLinux-10

[appstream-source]
name=AlmaLinux $releasever - AppStream - Source
mirrorlist=https://mirrors.almalinux.org/mirrorlist/$releasever/appstream-source
# baseurl=https://vault.almalinux.org/$releasever/AppStream/Source/
enabled=0
gpgcheck=1
gpgkey=file:///usr/share/distribution-gpg-keys/alma/RPM-GPG-KEY-AlmaLinux-10


[crb]
name=AlmaLinux $releasever - CRB
mirrorlist=https://mirrors.almalinux.org/mirrorlist/$releasever/crb{{ mirrorlist_arch }}
# baseurl=https://repo.almalinux.org/almalinux/$releasever/CRB/{{ baseurl_arch }}/os/
enabled=1
gpgcheck=1
countme=1
gpgkey=file:///usr/share/distribution-gpg-keys/alma/RPM-GPG-KEY-AlmaLinux-10

[crb-debuginfo]
name=AlmaLinux $releasever - CRB - Debug
mirrorlist=https://mirrors.almalinux.org/mirrorlist/$releasever/crb-debug{{ mirrorlist_arch }}
# baseurl=https://vault.almalinux.org/$releasever/CRB/debug/{{ baseurl_arch }}/
enabled=0
gpgcheck=1
gpgkey=file:///usr/share/distribution-gpg-keys/alma/RPM-GPG-KEY-AlmaLinux-10

[crb-source]
name=AlmaLinux $releasever - CRB - Source
mirrorlist=https://mirrors.almalinux.org/mirrorlist/$releasever/crb-source
# baseurl=https://vault.almalinux.org/$releasever/CRB/Source/
enabled=0
gpgcheck=1
gpgkey=file:///usr/share/distribution-gpg-keys/alma/RPM-GPG-KEY-AlmaLinux-10


[extras]
name=AlmaLinux $releasever - Extras
mirrorlist=https://mirrors.almalinux.org/mirrorlist/$releasever/extras{{ mirrorlist_arch }}
# baseurl=https://repo.almalinux.org/almalinux/$releasever/extras/{{ baseurl_arch }}/os/
enabled=1
gpgcheck=1
countme=1
gpgkey=file:///usr/share/distribution-gpg-keys/alma/RPM-GPG-KEY-AlmaLinux-10

[extras-debuginfo]
name=AlmaLinux $releasever - Extras - Debug
mirrorlist=https://mirrors.almalinux.org/mirrorlist/$releasever/extras-debug{{ mirrorlist_arch }}
# baseurl=https://vault.almalinux.org/$releasever/extras/debug/{{ baseurl_arch }}/
enabled=0
gpgcheck=1
gpgkey=file:///usr/share/distribution-gpg-keys/alma/RPM-GPG-KEY-AlmaLinux-10

[extras-source]
name=AlmaLinux $releasever - Extras - Source
mirrorlist=https://mirrors.almalinux.org/mirrorlist/$releasever/extras-source
# baseurl=https://vault.almalinux.org/$releasever/extras/Source/
enabled=0
gpgcheck=1
gpgkey=file:///usr/share/distribution-gpg-keys/alma/RPM-GPG-KEY-AlmaLinux-10


[devel]
name=AlmaLinux $releasever - Devel (WARNING: UNSUPPORTED - FOR BUILDROOT USE ONLY!)
mirrorlist=https://mirrors.almalinux.org/mirrorlist/$releasever/devel{{ mirrorlist_arch }}
# baseurl=https://repo.almalinux.org/almalinux/$releasever/devel/{{ baseurl_arch }}/os/
enabled=0
gpgcheck=1
gpgkey=file:///usr/share/distribution-gpg-keys/alma/RPM-GPG-KEY-AlmaLinux-10

[devel-debuginfo]
name=AlmaLinux $releasever - Devel debuginfo
mirrorlist=https://mirrors.almalinux.org/mirrorlist/$releasever/devel-debuginfo{{ mirrorlist_arch }}
# baseurl=https://repo.almalinux.org/almalinux/$releasever/devel/debug/{{ baseurl_arch }}/
enabled=0
gpgcheck=1
gpgkey=file:///usr/share/distribution-gpg-keys/alma/RPM-GPG-KEY-AlmaLinux-10

[devel-source]
name=AlmaLinux $releasever - Devel Source
mirrorlist=https://mirrors.almalinux.org/mirrorlist/$releasever/devel-source
# baseurl=https://repo.almalinux.org/almalinux/$releasever/devel/Source/
enabled=0
gpgcheck=1
gpgkey=file:///usr/share/distribution-gpg-keys/alma/RPM-GPG-KEY-AlmaLinux-10

"""
