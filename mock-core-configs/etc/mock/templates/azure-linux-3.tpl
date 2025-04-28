config_opts['chroot_setup_cmd'] = 'install bash binutils bzip2 coreutils cpio diffutils dnf findutils gawk glibc-devel grep gzip kernel-headers patch redhat-rpm-config rpm-build sed shadow-utils tar unzip util-linux which xz'
config_opts['dist'] = 'azl3'
config_opts['macros']['%dist'] = '.azl3'
config_opts['releasever'] = '3.0'
config_opts['package_manager'] = 'dnf'
config_opts['extra_chroot_dirs'] = [ '/run/lock', ]

# Disable copying ca-trust dirs on Azure Linux 3.0 to avoid any symlinks under the host's
# ca-trust dirs from turning into non-symlink'd dirs in the root and later conflicting
# with the symlink installed by the 'ca-certificates-shared' package.
config_opts['ssl_copied_ca_trust_dirs'] = None

# https://mcr.microsoft.com/en-us/product/azurelinux/base/core/tags:
# config_opts['bootstrap_image'] = 'mcr.microsoft.com/azurelinux/base/core:3.0'
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

[azurelinux-official-base]
name=Azure Linux Official Base $releasever $basearch
baseurl=https://packages.microsoft.com/azurelinux/$releasever/prod/base/$basearch
gpgkey=file:///usr/share/distribution-gpg-keys/azure-linux/MICROSOFT-RPM-GPG-KEY
gpgcheck=1
repo_gpgcheck=1
enabled=1

[azurelinux-official-extended]
name=Azure Linux Official Extended $releasever $basearch
baseurl=https://packages.microsoft.com/azurelinux/$releasever/prod/extended/$basearch
gpgkey=file:///usr/share/distribution-gpg-keys/azure-linux/MICROSOFT-RPM-GPG-KEY
gpgcheck=1
repo_gpgcheck=1
enabled=1

[azurelinux-official-ms-oss]
name=Azure Linux Official Microsoft Open-Source $releasever $basearch
baseurl=https://packages.microsoft.com/azurelinux/$releasever/prod/ms-oss/$basearch
gpgkey=file:///usr/share/distribution-gpg-keys/azure-linux/MICROSOFT-RPM-GPG-KEY
gpgcheck=1
repo_gpgcheck=1
enabled=1

[azurelinux-official-ms-non-oss]
name=Azure Linux Official Microsoft Non-Open-Source $releasever $basearch
baseurl=https://packages.microsoft.com/azurelinux/$releasever/prod/ms-non-oss/$basearch
gpgkey=file:///usr/share/distribution-gpg-keys/azure-linux/MICROSOFT-RPM-GPG-KEY
gpgcheck=1
repo_gpgcheck=1
enabled=1

"""
