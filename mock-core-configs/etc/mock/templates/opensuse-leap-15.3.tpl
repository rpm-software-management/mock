config_opts['chroot_setup_cmd'] = 'install patterns-devel-base-devel_rpm_build'
config_opts['dist'] = 'suse.lp153'  # only useful for --resultdir variable subst
config_opts['extra_chroot_dirs'] = [ '/run/lock', ]
config_opts['useradd'] = '/usr/sbin/useradd -o -m -u {{chrootuid}} -g {{chrootgid}} -d {{chroothome}} {{chrootuser}}'
config_opts['releasever'] = '15.3'
config_opts['macros']['%dist'] = '.suse.lp153'
config_opts['package_manager'] = 'dnf'
config_opts['bootstrap_image'] = 'registry.opensuse.org/opensuse/leap-dnf:15.3'
config_opts['ssl_ca_bundle_path'] = '/var/lib/ca-certificates/ca-bundle.pem'

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
{% if target_arch == 'x86_64' %}
excludepkgs=*.i586,*.i686,*.ppc,*.ppc64,*.ppc64le,*.s390x
{% elif target_arch == 'i586' %}
excludepkgs=*.x86_64,*.ppc,*.ppc64,*.ppc64le,*.s390x
{% elif target_arch == 'ppc64le' %}
excludepkgs=*.ppc,*.ppc64,*.x86_64,*.i586,*.i686,*.s390x
{% elif target_arch == 'ppc64' %}
excludepkgs=*.ppc,*.ppc64le,*.x86_64,*.i586,*.i686,*.s390x
{% elif target_arch == 's390x' %}
excludepkgs=*.ppc,*.ppc64,*.ppc64le,*.x86_64,*.i586,*.i686
{% endif %}

protected_packages=
user_agent={{ user_agent }}

# repos

[opensuse-leap-oss]
name=openSUSE Leap $releasever - {{ target_arch }} - OSS
baseurl=http://download.opensuse.org/distribution/leap/$releasever/repo/oss/
#metalink=http://download.opensuse.org/distribution/leap/$releasever/repo/oss/repodata/repomd.xml.metalink
enabled=1
gpgkey=file:///usr/share/distribution-gpg-keys/opensuse/RPM-GPG-KEY-openSUSE
        file:///usr/share/distribution-gpg-keys/opensuse/RPM-GPG-KEY-openSUSE-Backports
        file:///usr/share/distribution-gpg-keys/suse/RPM-GPG-KEY-SuSE-SLE-15
gpgcheck=1

[opensuse-leap-oss-update]
name=openSUSE Leap $releasever - {{ target_arch }} - OSS - Updates
baseurl=http://download.opensuse.org/update/leap/$releasever/oss/
#metalink=http://download.opensuse.org/update/leap/$releasever/oss/repodata/repomd.xml.metalink
enabled=1
gpgkey=file:///usr/share/distribution-gpg-keys/opensuse/RPM-GPG-KEY-openSUSE
gpgcheck=1

[opensuse-leap-sle-update]
name=openSUSE Leap $releasever - {{ target_arch }} - Updates from SUSE Linux Enterprise
baseurl=http://download.opensuse.org/update/leap/$releasever/sle/
#metalink=http://download.opensuse.org/update/leap/$releasever/sle/repodata/repomd.xml.metalink
enabled=1
gpgkey=file:///usr/share/distribution-gpg-keys/suse/RPM-GPG-KEY-SuSE-SLE-15
gpgcheck=1

[opensuse-leap-sle-backports-update]
name=openSUSE Leap $releasever - {{ target_arch }} - Updates from Backports for SUSE Linux Enterprise
baseurl=http://download.opensuse.org/update/leap/$releasever/backports/
#metalink=http://download.opensuse.org/update/leap/$releasever/backports/repodata/repomd.xml.metalink
enabled=1
gpgkey=file:///usr/share/distribution-gpg-keys/opensuse/RPM-GPG-KEY-openSUSE-Backports
gpgcheck=1

"""
