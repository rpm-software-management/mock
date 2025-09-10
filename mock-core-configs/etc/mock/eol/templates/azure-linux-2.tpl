config_opts['chroot_setup_cmd'] = 'install bash binutils bzip2 coreutils cpio diffutils dnf findutils gawk glibc-devel grep gzip kernel-headers patch redhat-rpm-config rpm-build sed shadow-utils tar unzip util-linux which xz'
config_opts['dist'] = 'cm2'
config_opts['releasever'] = '2.0'
config_opts['package_manager'] = 'dnf'
config_opts['extra_chroot_dirs'] = [ '/run/lock', ]

# https://mcr.microsoft.com/en-us/product/cbl-mariner/base/core/tags:
# config_opts['bootstrap_image'] = 'mcr.microsoft.com/cbl-mariner/base/core:2.0'
# Container image contains tdnf (https://github.com/vmware/tdnf) as the base package manager so it can't be used:
config_opts['use_bootstrap'] = False

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
module_platform_id=platform:2.9
user_agent={{ user_agent }}

[mariner-official-base]
name=CBL-Mariner Official Base $releasever $basearch
baseurl=https://packages.microsoft.com/cbl-mariner/$releasever/prod/base/$basearch
gpgkey=file:///usr/share/distribution-gpg-keys/azure-linux/MICROSOFT-RPM-GPG-KEY file:///usr/share/distribution-gpg-keys/azure-linux/MICROSOFT-METADATA-GPG-KEY
gpgcheck=1
repo_gpgcheck=1
enabled=1

[mariner-official-extras]
name=CBL-Mariner Official Extras $releasever $basearch
baseurl=https://packages.microsoft.com/cbl-mariner/$releasever/prod/extras/$basearch
gpgkey=file:///usr/share/distribution-gpg-keys/azure-linux/MICROSOFT-RPM-GPG-KEY file:///usr/share/distribution-gpg-keys/azure-linux/MICROSOFT-METADATA-GPG-KEY
gpgcheck=1
repo_gpgcheck=1
enabled=1

[mariner-official-extended]
name=CBL-Mariner Official Extended $releasever $basearch
baseurl=https://packages.microsoft.com/cbl-mariner/$releasever/prod/extended/$basearch
gpgkey=file:///usr/share/distribution-gpg-keys/azure-linux/MICROSOFT-RPM-GPG-KEY file:///usr/share/distribution-gpg-keys/azure-linux/MICROSOFT-METADATA-GPG-KEY
gpgcheck=1
repo_gpgcheck=1
enabled=1

[mariner-official-microsoft]
name=CBL-Mariner Official Microsoft $releasever $basearch
baseurl=https://packages.microsoft.com/cbl-mariner/$releasever/prod/Microsoft/$basearch
gpgkey=file:///usr/share/distribution-gpg-keys/azure-linux/MICROSOFT-RPM-GPG-KEY file:///usr/share/distribution-gpg-keys/azure-linux/MICROSOFT-METADATA-GPG-KEY
gpgcheck=1
repo_gpgcheck=1
enabled=1

"""
