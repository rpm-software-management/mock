# Same set as the openSUSE patterns-devel-base-devel_rpm_build pattern, which
# does not exist in SUSE Linux Enterprise.
config_opts['chroot_setup_cmd'] = 'install libnss_usrfiles2 man netcfg rpm-build SLES-release'
config_opts['dist'] = 'sles16.0'  # only useful for --resultdir variable subst
config_opts['extra_chroot_dirs'] = [ '/run/lock', ]
config_opts['releasever'] = '16.0'
config_opts['package_manager'] = 'dnf5'
config_opts['ssl_ca_bundle_path'] = '/var/lib/ca-certificates/ca-bundle.pem'
config_opts['description'] = 'SUSE Linux Enterprise Server {{ releasever }}'

# Repositories come from the SUSE Customer Center, see
# https://rpm-software-management.github.io/mock/Feature-slechroots
# SLES 16 has no modules anymore; everything is in the product repository.
config_opts['suse_subscription_required'] = True
config_opts['suse_subscription_product'] = 'SLES'
config_opts['suse_subscription_version'] = '16.0'
config_opts['suse_subscription_gpgkey'] = 'file:///usr/share/distribution-gpg-keys/suse/RPM-GPG-KEY-SuSE-ALP-Main'

# dnf5 is only shipped in SUSE Package Hub, whose packages are signed by the
# openSUSE Backports key.  Package Hub is only enabled in the bootstrap chroot,
# which is installed by the host's package manager (the SUSE container images
# only contain zypper), so the buildroot is made of SUSE supported packages only.
config_opts['use_bootstrap_image'] = False
config_opts['suse_subscription_bootstrap_extensions'] = ['PackageHub']
config_opts['suse_subscription_bootstrap_gpgkey'] = 'file:///usr/share/distribution-gpg-keys/opensuse/RPM-GPG-KEY-openSUSE-16-Backports'

# The bootstrap chroot is installed by the host's RPM: create its database in
# the native SUSE format.
config_opts['installation_rpm_macros'] = {'%_db_backend': 'ndb'}

# dnf-data's %post calls ln without requiring coreutils, so install coreutils
# in a separate transaction before the package manager.
config_opts['dnf5_install_command'] = 'install coreutils'
config_opts['bootstrap_chroot_additional_packages'] = ['dnf5', 'dnf5-plugins']

config_opts['dnf.conf'] = """
[main]
keepcache=1
debuglevel=2
reposdir=/dev/null
logfile=/var/log/yum.log
retries=20
obsoletes=1
gpgcheck=1
assumeyes=1
syslog_ident=mock
syslog_device=
install_weak_deps=0
metadata_expire=0
best=1

protected_packages=
user_agent={{ user_agent }}

# repos, generated from the SUSE Customer Center at every mock run

{{ suse_subscription_repos }}
"""
