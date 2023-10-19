config_opts['releasever'] = 'eln'
config_opts['eln_rawhide_releasever'] = '40'

config_opts['root'] = 'fedora-eln-{{ target_arch }}'

# Fedora ELN i386 doesn't get composes (isn't mirrored on
# odcs.fedoraproject.org), we need to build using the Koji buildroot.
# Note that similar idiom used in fedora-branched.tpl and fedora-rawhide.tpl.
config_opts['mirrored'] = config_opts['target_arch'] != 'i686'

config_opts['chroot_setup_cmd'] = 'install bash bzip2 coreutils cpio diffutils fedora-release-eln findutils gawk glibc-minimal-langpack grep gzip info patch redhat-rpm-config rpm-build sed tar unzip util-linux which xz'

config_opts['dist'] = 'eln'  # only useful for --resultdir variable subst
config_opts['extra_chroot_dirs'] = [ '/run/lock', ]
config_opts['package_manager'] = 'dnf'

# Per https://github.com/fedora-eln/eln/issues/164 updated up to 4 times a day.
# Docs: https://docs.fedoraproject.org/en-US/eln/deliverables/#_container_image
config_opts['bootstrap_image'] = 'quay.io/fedoraci/fedora:eln'
# Per https://github.com/fedora-eln/eln/issues/166
config_opts['bootstrap_image_ready'] = True

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
{%- for version in [eln_rawhide_releasever|int, eln_rawhide_releasever|int - 1, eln_rawhide_releasever|int - 2]
%} file:///usr/share/distribution-gpg-keys/fedora/RPM-GPG-KEY-fedora-{{ version }}-primary
{%- endfor %}
{%- endmacro %}

{% if mirrored %}
[eln-baseos]
name=Fedora - ELN BaseOS - Developmental packages for the next Enterprise Linux release
baseurl=https://odcs.fedoraproject.org/composes/production/latest-Fedora-ELN/compose/BaseOS/$basearch/os/
#metalink=https://mirrors.fedoraproject.org/metalink?repo=eln&arch=$basearch
enabled=1
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
enabled=1
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



[eln-extras]
name=Fedora - ELN Extras - Developmental packages for the next Enterprise Linux release
baseurl=https://odcs.fedoraproject.org/composes/production/latest-Fedora-ELN/compose/Extras/$basearch/os/
#metalink=https://mirrors.fedoraproject.org/metalink?repo=eln&arch=$basearch
enabled=1
countme=1
metadata_expire=6h
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-fedora-eln-$basearch
skip_if_unavailable=False

[eln-extras-debuginfo]
name=Fedora - ELN Extras - Debug
baseurl=https://odcs.fedoraproject.org/composes/production/latest-Fedora-ELN/compose/Extras/$basearch/debug/tree
#metalink=https://mirrors.fedoraproject.org/metalink?repo=eln-debug&arch=$basearch
enabled=0
metadata_expire=6h
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-fedora-eln-$basearch
skip_if_unavailable=False

[eln-extras-source]
name=Fedora - ELN Extras - Source
baseurl=https://odcs.fedoraproject.org/composes/production/latest-Fedora-ELN/compose/Extras/source/tree/
#metalink=https://mirrors.fedoraproject.org/metalink?repo=eln-source&arch=$basearch
enabled=0
metadata_expire=6h
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-fedora-eln-$basearch
skip_if_unavailable=False



[eln-ha]
name=Fedora - ELN HighAvailability - Developmental packages for the next Enterprise Linux release
baseurl=https://odcs.fedoraproject.org/composes/production/latest-Fedora-ELN/compose/HighAvailability/$basearch/os/
#metalink=https://mirrors.fedoraproject.org/metalink?repo=eln&arch=$basearch
enabled=0
countme=1
metadata_expire=6h
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-fedora-eln-$basearch
skip_if_unavailable=False

[eln-ha-debuginfo]
name=Fedora - ELN HighAvailability - Debug
baseurl=https://odcs.fedoraproject.org/composes/production/latest-Fedora-ELN/compose/HighAvailability/$basearch/debug/tree
#metalink=https://mirrors.fedoraproject.org/metalink?repo=eln-debug&arch=$basearch
enabled=0
metadata_expire=6h
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-fedora-eln-$basearch
skip_if_unavailable=False

[eln-ha-source]
name=Fedora - ELN HighAvailability - Source
baseurl=https://odcs.fedoraproject.org/composes/production/latest-Fedora-ELN/compose/HighAvailability/source/tree/
#metalink=https://mirrors.fedoraproject.org/metalink?repo=eln-source&arch=$basearch
enabled=0
metadata_expire=6h
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-fedora-eln-$basearch
skip_if_unavailable=False



[eln-rs]
name=Fedora - ELN ResilientStorage - Developmental packages for the next Enterprise Linux release
baseurl=https://odcs.fedoraproject.org/composes/production/latest-Fedora-ELN/compose/ResilientStorage/$basearch/os/
#metalink=https://mirrors.fedoraproject.org/metalink?repo=eln&arch=$basearch
enabled=0
countme=1
metadata_expire=6h
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-fedora-eln-$basearch
skip_if_unavailable=False

[eln-rs-debuginfo]
name=Fedora - ELN ResilientStorage - Debug
baseurl=https://odcs.fedoraproject.org/composes/production/latest-Fedora-ELN/compose/ResilientStorage/$basearch/debug/tree
#metalink=https://mirrors.fedoraproject.org/metalink?repo=eln-debug&arch=$basearch
enabled=0
metadata_expire=6h
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-fedora-eln-$basearch
skip_if_unavailable=False

[eln-rs-source]
name=Fedora - ELN ResilientStorage - Source
baseurl=https://odcs.fedoraproject.org/composes/production/latest-Fedora-ELN/compose/ResilientStorage/source/tree/
#metalink=https://mirrors.fedoraproject.org/metalink?repo=eln-source&arch=$basearch
enabled=0
metadata_expire=6h
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-fedora-eln-$basearch
skip_if_unavailable=False



[eln-rt]
name=Fedora - ELN RT - Developmental packages for the next Enterprise Linux release
baseurl=https://odcs.fedoraproject.org/composes/production/latest-Fedora-ELN/compose/RT/$basearch/os/
#metalink=https://mirrors.fedoraproject.org/metalink?repo=eln&arch=$basearch
enabled=0
countme=1
metadata_expire=6h
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-fedora-eln-$basearch
skip_if_unavailable=False

[eln-rt-debuginfo]
name=Fedora - ELN RT - Debug
baseurl=https://odcs.fedoraproject.org/composes/production/latest-Fedora-ELN/compose/RT/$basearch/debug/tree
#metalink=https://mirrors.fedoraproject.org/metalink?repo=eln-debug&arch=$basearch
enabled=0
metadata_expire=6h
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-fedora-eln-$basearch
skip_if_unavailable=False

[eln-rt-source]
name=Fedora - ELN RT - Source
baseurl=https://odcs.fedoraproject.org/composes/production/latest-Fedora-ELN/compose/RT/source/tree/
#metalink=https://mirrors.fedoraproject.org/metalink?repo=eln-source&arch=$basearch
enabled=0
metadata_expire=6h
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-fedora-eln-$basearch
skip_if_unavailable=False



[eln-nfv]
name=Fedora - ELN NFV - Developmental packages for the next Enterprise Linux release
baseurl=https://odcs.fedoraproject.org/composes/production/latest-Fedora-ELN/compose/NFV/$basearch/os/
#metalink=https://mirrors.fedoraproject.org/metalink?repo=eln&arch=$basearch
enabled=0
countme=1
metadata_expire=6h
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-fedora-eln-$basearch
skip_if_unavailable=False

[eln-nfv-debuginfo]
name=Fedora - ELN NFV - Debug
baseurl=https://odcs.fedoraproject.org/composes/production/latest-Fedora-ELN/compose/NFV/$basearch/debug/tree
#metalink=https://mirrors.fedoraproject.org/metalink?repo=eln-debug&arch=$basearch
enabled=0
metadata_expire=6h
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-fedora-eln-$basearch
skip_if_unavailable=False

[eln-nfv-source]
name=Fedora - ELN NFV - Source
baseurl=https://odcs.fedoraproject.org/composes/production/latest-Fedora-ELN/compose/NFV/source/tree/
#metalink=https://mirrors.fedoraproject.org/metalink?repo=eln-source&arch=$basearch
enabled=0
metadata_expire=6h
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-fedora-eln-$basearch
skip_if_unavailable=False



[eln-sap]
name=Fedora - ELN SAP - Developmental packages for the next Enterprise Linux release
baseurl=https://odcs.fedoraproject.org/composes/production/latest-Fedora-ELN/compose/SAP/$basearch/os/
#metalink=https://mirrors.fedoraproject.org/metalink?repo=eln&arch=$basearch
enabled=0
countme=1
metadata_expire=6h
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-fedora-eln-$basearch
skip_if_unavailable=False

[eln-sap-debuginfo]
name=Fedora - ELN SAP - Debug
baseurl=https://odcs.fedoraproject.org/composes/production/latest-Fedora-ELN/compose/SAP/$basearch/debug/tree
#metalink=https://mirrors.fedoraproject.org/metalink?repo=eln-debug&arch=$basearch
enabled=0
metadata_expire=6h
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-fedora-eln-$basearch
skip_if_unavailable=False

[eln-sap-source]
name=Fedora - ELN SAP - Source
baseurl=https://odcs.fedoraproject.org/composes/production/latest-Fedora-ELN/compose/SAP/source/tree/
#metalink=https://mirrors.fedoraproject.org/metalink?repo=eln-source&arch=$basearch
enabled=0
metadata_expire=6h
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-fedora-eln-$basearch
skip_if_unavailable=False



[eln-saphana]
name=Fedora - ELN SAPHANA - Developmental packages for the next Enterprise Linux release
baseurl=https://odcs.fedoraproject.org/composes/production/latest-Fedora-ELN/compose/SAPHANA/$basearch/os/
#metalink=https://mirrors.fedoraproject.org/metalink?repo=eln&arch=$basearch
enabled=0
countme=1
metadata_expire=6h
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-fedora-eln-$basearch
skip_if_unavailable=False

[eln-saphana-debuginfo]
name=Fedora - ELN SAPHANA - Debug
baseurl=https://odcs.fedoraproject.org/composes/production/latest-Fedora-ELN/compose/SAPHANA/$basearch/debug/tree
#metalink=https://mirrors.fedoraproject.org/metalink?repo=eln-debug&arch=$basearch
enabled=0
metadata_expire=6h
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-fedora-eln-$basearch
skip_if_unavailable=False

[eln-saphana-source]
name=Fedora - ELN SAPHANA - Source
baseurl=https://odcs.fedoraproject.org/composes/production/latest-Fedora-ELN/compose/SAPHANA/source/tree/
#metalink=https://mirrors.fedoraproject.org/metalink?repo=eln-source&arch=$basearch
enabled=0
metadata_expire=6h
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-fedora-eln-$basearch
skip_if_unavailable=False
{% endif %}

[local]
name=local
baseurl=https://kojipkgs.fedoraproject.org/repos/eln-build/latest/$basearch/
cost=2000
enabled={{ not mirrored }}
skip_if_unavailable=False
"""
