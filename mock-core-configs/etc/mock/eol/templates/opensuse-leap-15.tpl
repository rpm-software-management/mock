config_opts['root'] = 'opensuse-leap-{{ releasever }}-{{ target_arch }}'

config_opts['chroot_setup_cmd'] = 'install patterns-devel-base-devel_rpm_build'
config_opts['dist'] = 'suse.lp{{ releasever|replace(".", "") }}'  # only useful for --resultdir variable subst
config_opts['extra_chroot_dirs'] = [ '/run/lock', ]
config_opts['macros']['%dist'] = '.suse.lp{{ releasever|replace(".", "") }}'
config_opts['package_manager'] = 'dnf'
config_opts['bootstrap_image'] = 'registry.opensuse.org/opensuse/leap-dnf:{{ releasever }}'
config_opts['ssl_ca_bundle_path'] = '/var/lib/ca-certificates/ca-bundle.pem'
config_opts['description'] = 'openSUSE Leap {{ releasever }}'

# Leap 15.3 is the first release built from the SLE binaries. Before it, the
# non-x86_64 architectures were ports, and there were no SLE update repositories
# and no leap-dnf images.
config_opts['leap_sle_binaries'] = config_opts['releasever'] not in ('15.0', '15.1', '15.2')
if not config_opts['leap_sle_binaries']:
    config_opts['use_bootstrap_image'] = False
    # Create the bootstrap database in the native SUSE format.
    config_opts['installation_rpm_macros'] = {'%_db_backend': 'ndb'}
    # Keep the buildroot database in /var/lib/rpm, as the rpm %posttrans
    # migration to /usr/lib/sysimage/rpm overwrites an existing database there.
    config_opts['files']['etc/rpm/macros.db_backend'] = """
%_db_backend ndb
%_dbpath /var/lib/rpm
"""

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
{% if repo_arch == 'x86_64' %}
excludepkgs=*.i586,*.i686,*.ppc,*.ppc64,*.ppc64le,*.s390x
{% elif repo_arch == 'i586' %}
excludepkgs=*.x86_64,*.ppc,*.ppc64,*.ppc64le,*.s390x
{% elif repo_arch == 'ppc64le' %}
excludepkgs=*.ppc,*.ppc64,*.x86_64,*.i586,*.i686,*.s390x
{% elif repo_arch == 'ppc64' %}
excludepkgs=*.ppc,*.ppc64le,*.x86_64,*.i586,*.i686,*.s390x
{% elif repo_arch == 's390x' %}
excludepkgs=*.ppc,*.ppc64,*.ppc64le,*.x86_64,*.i586,*.i686
{% endif %}

{# The dnf 2.7 of Leap 15.0 turns an empty value into None. -#}
protected_packages={% if releasever == '15.0' %},{% endif %}
user_agent={{ user_agent }}

# repos

[opensuse-leap-oss]
name=openSUSE Leap $releasever - {{ repo_arch }} - OSS
baseurl=https://cdn.opensuse.org/{% if not leap_sle_binaries and repo_arch != 'x86_64' %}ports/{{ repo_arch }}/{% endif %}distribution/leap/$releasever/repo/oss/
#metalink=https://cdn.opensuse.org/{% if not leap_sle_binaries and repo_arch != 'x86_64' %}ports/{{ repo_arch }}/{% endif %}distribution/leap/$releasever/repo/oss/repodata/repomd.xml.metalink
enabled=1
gpgkey=file:///usr/share/distribution-gpg-keys/opensuse/RPM-GPG-KEY-openSUSE
        file:///usr/share/distribution-gpg-keys/opensuse/RPM-GPG-KEY-openSUSE-2022
        file:///usr/share/distribution-gpg-keys/opensuse/RPM-GPG-KEY-openSUSE-Backports
        file:///usr/share/distribution-gpg-keys/opensuse/RPM-GPG-KEY-openSUSE-Backports-2023
        file:///usr/share/distribution-gpg-keys/suse/RPM-GPG-KEY-SuSE-SLE-15
        file:///usr/share/distribution-gpg-keys/suse/RPM-GPG-KEY-SuSE-SLE-Main-2023
gpgcheck=1

[opensuse-leap-oss-update]
name=openSUSE Leap $releasever - {{ repo_arch }} - OSS - Updates
baseurl=https://cdn.opensuse.org/{% if not leap_sle_binaries and repo_arch != 'x86_64' %}ports/{% endif %}update/leap/$releasever/oss/
#metalink=https://cdn.opensuse.org/{% if not leap_sle_binaries and repo_arch != 'x86_64' %}ports/{% endif %}update/leap/$releasever/oss/repodata/repomd.xml.metalink
enabled=1
gpgkey=file:///usr/share/distribution-gpg-keys/opensuse/RPM-GPG-KEY-openSUSE
        file:///usr/share/distribution-gpg-keys/opensuse/RPM-GPG-KEY-openSUSE-2022
gpgcheck=1
{% if leap_sle_binaries %}
[opensuse-leap-sle-update]
name=openSUSE Leap $releasever - {{ repo_arch }} - Updates from SUSE Linux Enterprise
baseurl=https://cdn.opensuse.org/update/leap/$releasever/sle/
#metalink=https://cdn.opensuse.org/update/leap/$releasever/sle/repodata/repomd.xml.metalink
enabled=1
gpgkey=file:///usr/share/distribution-gpg-keys/suse/RPM-GPG-KEY-SuSE-SLE-15
        file:///usr/share/distribution-gpg-keys/suse/RPM-GPG-KEY-SuSE-SLE-Main-2023
gpgcheck=1

[opensuse-leap-sle-backports-update]
name=openSUSE Leap $releasever - {{ repo_arch }} - Updates from Backports for SUSE Linux Enterprise
baseurl=https://cdn.opensuse.org/update/leap/$releasever/backports/
#metalink=https://cdn.opensuse.org/update/leap/$releasever/backports/repodata/repomd.xml.metalink
enabled=1
gpgkey=file:///usr/share/distribution-gpg-keys/opensuse/RPM-GPG-KEY-openSUSE-Backports
        file:///usr/share/distribution-gpg-keys/opensuse/RPM-GPG-KEY-openSUSE-Backports-2023
gpgcheck=1
{% endif %}
"""
