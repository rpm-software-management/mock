config_opts['releasever'] = 'eln'
config_opts['eln_rawhide_releasever'] = '36'

config_opts['root'] = 'fedora-eln-{{ target_arch }}'

config_opts['chroot_setup_cmd'] = 'install bash bzip2 coreutils cpio diffutils fedora-release-eln findutils gawk glibc-minimal-langpack grep gzip info patch redhat-rpm-config rpm-build sed shadow-utils tar unzip util-linux which xz'

config_opts['dist'] = 'eln'  # only useful for --resultdir variable subst
config_opts['extra_chroot_dirs'] = [ '/run/lock', ]
config_opts['package_manager'] = 'dnf'
config_opts['bootstrap_image'] = 'fedora:latest'

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
user_agent={{ user_agent }}

# TODO
module_platform_id=platform:eln
protected_packages=

{%- macro rawhide_gpg_keys() -%}
file:///usr/share/distribution-gpg-keys/fedora/RPM-GPG-KEY-fedora-rawhide-primary
{%- for version in [eln_rawhide_releasever|int, eln_rawhide_releasever|int - 1]
%} file:///usr/share/distribution-gpg-keys/fedora/RPM-GPG-KEY-fedora-{{ version }}-primary
{%- endfor %}
{%- endmacro %}

# repos
# The Everything repository have to be enabled to get all of the packages because
# some of them are not present anywhere else. Also the AppStream repository
# have to be enabled because it contain modules. Everything else is not required.
[local]
name=local
baseurl=https://kojipkgs.fedoraproject.org/repos/eln-build/latest/$basearch/
cost=2000
enabled=0
skip_if_unavailable=False

[eln]
name=Fedora - ELN - Developmental packages for the next Enterprise Linux release
baseurl=https://odcs.fedoraproject.org/composes/production/latest-Fedora-ELN/compose/Everything/$basearch/os/
#metalink=https://mirrors.fedoraproject.org/metalink?repo=eln&arch=$basearch
enabled=1
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey={{ rawhide_gpg_keys() }}
skip_if_unavailable=False

[eln-debuginfo]
name=Fedora - ELN - Debug
baseurl=https://odcs.fedoraproject.org/composes/production/latest-Fedora-ELN/compose/Everything/$basearch/debug/tree
#metalink=https://mirrors.fedoraproject.org/metalink?repo=eln-debug&arch=$basearch
enabled=0
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey={{ rawhide_gpg_keys() }}
skip_if_unavailable=False

[eln-source]
name=Fedora - ELN - Source
baseurl=https://odcs.fedoraproject.org/composes/production/latest-Fedora-ELN/compose/Everything/source/tree/
#metalink=https://mirrors.fedoraproject.org/metalink?repo=eln-source&arch=$basearch
enabled=0
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey={{ rawhide_gpg_keys() }}
skip_if_unavailable=False


[eln-baseos]
name=Fedora - ELN BaseOS - Developmental packages for the next Enterprise Linux release
baseurl=https://odcs.fedoraproject.org/composes/production/latest-Fedora-ELN/compose/BaseOS/$basearch/os/
#metalink=https://mirrors.fedoraproject.org/metalink?repo=eln&arch=$basearch
enabled=0
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey={{ rawhide_gpg_keys() }}
skip_if_unavailable=False

[eln-baseos-debuginfo]
name=Fedora - ELN BaseOS - Debug
baseurl=https://odcs.fedoraproject.org/composes/production/latest-Fedora-ELN/compose/BaseOS/$basearch/debug/tree
#metalink=https://mirrors.fedoraproject.org/metalink?repo=eln-debug&arch=$basearch
enabled=0
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey={{ rawhide_gpg_keys() }}
skip_if_unavailable=False

[eln-baseos-source]
name=Fedora - ELN BaseOS - Source
baseurl=https://odcs.fedoraproject.org/composes/production/latest-Fedora-ELN/compose/BaseOS/source/tree/
#metalink=https://mirrors.fedoraproject.org/metalink?repo=eln-source&arch=$basearch
enabled=0
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey={{ rawhide_gpg_keys() }}
skip_if_unavailable=False


[eln-appstream]
name=Fedora - ELN AppStream - Developmental packages for the next Enterprise Linux release
baseurl=https://odcs.fedoraproject.org/composes/production/latest-Fedora-ELN/compose/AppStream/$basearch/os/
#metalink=https://mirrors.fedoraproject.org/metalink?repo=eln&arch=$basearch
enabled=1
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey={{ rawhide_gpg_keys() }}
skip_if_unavailable=False

[eln-appstream-debuginfo]
name=Fedora - ELN AppStream - Debug
baseurl=https://odcs.fedoraproject.org/composes/production/latest-Fedora-ELN/compose/AppStream/$basearch/debug/tree
#metalink=https://mirrors.fedoraproject.org/metalink?repo=eln-debug&arch=$basearch
enabled=0
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey={{ rawhide_gpg_keys() }}
skip_if_unavailable=False

[eln-appstream-source]
name=Fedora - ELN AppStream - Source
baseurl=https://odcs.fedoraproject.org/composes/production/latest-Fedora-ELN/compose/AppStream/source/tree/
#metalink=https://mirrors.fedoraproject.org/metalink?repo=eln-source&arch=$basearch
enabled=0
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey={{ rawhide_gpg_keys() }}
skip_if_unavailable=False


[eln-crb]
name=Fedora - ELN CodeReady Linux Builders - Build packages for the next Enterprise Linux release
baseurl=https://odcs.fedoraproject.org/composes/production/latest-Fedora-ELN/compose/CRB/$basearch/os/
#metalink=https://mirrors.fedoraproject.org/metalink?repo=eln&arch=$basearch
enabled=0
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey={{ rawhide_gpg_keys() }}
skip_if_unavailable=False

[eln-crb-debuginfo]
name=Fedora - ELN CodeReady Linux Builders - Debug
baseurl=https://odcs.fedoraproject.org/composes/production/latest-Fedora-ELN/compose/CRB/$basearch/debug/tree
#metalink=https://mirrors.fedoraproject.org/metalink?repo=eln-debug&arch=$basearch
enabled=0
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey={{ rawhide_gpg_keys() }}
skip_if_unavailable=False

[eln-crb-source]
name=Fedora - ELN CodeReady Linux Builders - Source
baseurl=https://odcs.fedoraproject.org/composes/production/latest-Fedora-ELN/compose/CRB/source/tree/
#metalink=https://mirrors.fedoraproject.org/metalink?repo=eln-source&arch=$basearch
enabled=0
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey={{ rawhide_gpg_keys() }}
skip_if_unavailable=False
"""
