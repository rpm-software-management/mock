config_opts['releasever'] = 'eln'
config_opts['eln_rawhide_releasever'] = '45'

config_opts['root'] = 'fedora-eln-{{ target_arch }}'

config_opts['chroot_setup_cmd'] = 'install bash bzip2 coreutils cpio diffutils fedora-release-eln findutils gawk glibc-minimal-langpack grep gzip info patch redhat-rpm-config rpm-build sed tar unzip util-linux which xz'

config_opts['dist'] = 'eln'  # only useful for --resultdir variable subst
config_opts['extra_chroot_dirs'] = [ '/run/lock', ]

# https://fedoraproject.org/wiki/Changes/BuildWithDNF5
# https://pagure.io/releng/issue/11895
config_opts['package_manager'] = 'dnf5'

# Per https://github.com/fedora-eln/eln/issues/164 updated up to 4 times a day.
# Docs: https://docs.fedoraproject.org/en-US/eln/deliverables/#_container_image
config_opts['bootstrap_image'] = 'quay.io/fedora/eln:latest'

# https://fedoraproject.org/wiki/Changes/ReplaceDnfWithDnf5 applied to ELN!
config_opts['bootstrap_image_ready'] = True

config_opts['dnf.conf'] = """
[main]
keepcache=1
system_cachedir=/var/cache/dnf
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

[eln-baseos]
name=Fedora - ELN BaseOS - Developmental packages for the next Enterprise Linux release
#baseurl=https://dl.fedoraproject.org/pub/eln/1/BaseOS/$basearch/os/
metalink=https://mirrors.fedoraproject.org/metalink?repo=eln-baseos-1&arch=$basearch
enabled=1
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey={{ rawhide_gpg_keys() }}
skip_if_unavailable=False

[eln-baseos-debuginfo]
name=Fedora - ELN BaseOS - Debug
#baseurl=https://dl.fedoraproject.org/pub/eln/1/BaseOS/$basearch/debug/tree
metalink=https://mirrors.fedoraproject.org/metalink?repo=eln-baseos-debug-1&arch=$basearch
enabled=0
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey={{ rawhide_gpg_keys() }}
skip_if_unavailable=False

[eln-baseos-source]
name=Fedora - ELN BaseOS - Source
#baseurl=https://dl.fedoraproject.org/pub/eln/1/BaseOS/source/tree/
metalink=https://mirrors.fedoraproject.org/metalink?repo=eln-baseos-source-1&arch=source
enabled=0
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey={{ rawhide_gpg_keys() }}
skip_if_unavailable=False


[eln-appstream]
name=Fedora - ELN AppStream - Developmental packages for the next Enterprise Linux release
#baseurl=https://dl.fedoraproject.org/pub/eln/1/AppStream/$basearch/os/
metalink=https://mirrors.fedoraproject.org/metalink?repo=eln-appstream-1&arch=$basearch
enabled=1
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey={{ rawhide_gpg_keys() }}
skip_if_unavailable=False

[eln-appstream-debuginfo]
name=Fedora - ELN AppStream - Debug
#baseurl=https://dl.fedoraproject.org/pub/eln/1/AppStream/$basearch/debug/tree
metalink=https://mirrors.fedoraproject.org/metalink?repo=eln-appstream-debug-1&arch=$basearch
enabled=0
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey={{ rawhide_gpg_keys() }}
skip_if_unavailable=False

[eln-appstream-source]
name=Fedora - ELN AppStream - Source
#baseurl=https://dl.fedoraproject.org/pub/eln/1/AppStream/source/tree/
metalink=https://mirrors.fedoraproject.org/metalink?repo=eln-appstream-source-1&arch=source
enabled=0
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey={{ rawhide_gpg_keys() }}
skip_if_unavailable=False


[eln-crb]
name=Fedora - ELN CodeReady Linux Builders - Build packages for the next Enterprise Linux release
#baseurl=https://dl.fedoraproject.org/pub/eln/1/CRB/$basearch/os/
metalink=https://mirrors.fedoraproject.org/metalink?repo=eln-crb-1&arch=$basearch
enabled=1
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey={{ rawhide_gpg_keys() }}
skip_if_unavailable=False

[eln-crb-debuginfo]
name=Fedora - ELN CodeReady Linux Builders - Debug
#baseurl=https://dl.fedoraproject.org/pub/eln/1/CRB/$basearch/debug/tree
metalink=https://mirrors.fedoraproject.org/metalink?repo=eln-crb-debug-1&arch=$basearch
enabled=0
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey={{ rawhide_gpg_keys() }}
skip_if_unavailable=False

[eln-crb-source]
name=Fedora - ELN CodeReady Linux Builders - Source
#baseurl=https://dl.fedoraproject.org/pub/eln/1/CRB/source/tree/
metalink=https://mirrors.fedoraproject.org/metalink?repo=eln-crb-source-1&arch=source
enabled=0
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey={{ rawhide_gpg_keys() }}
skip_if_unavailable=False



[eln-extras]
name=Fedora - ELN Extras - Developmental packages for the next Enterprise Linux release
#baseurl=https://dl.fedoraproject.org/pub/eln/1/Extras/$basearch/os/
metalink=https://mirrors.fedoraproject.org/metalink?repo=eln-extras-1&arch=$basearch
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
#baseurl=https://dl.fedoraproject.org/pub/eln/1/Extras/$basearch/debug/tree
metalink=https://mirrors.fedoraproject.org/metalink?repo=eln-extras-debug-1&arch=$basearch
enabled=0
metadata_expire=6h
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-fedora-eln-$basearch
skip_if_unavailable=False

[eln-extras-source]
name=Fedora - ELN Extras - Source
#baseurl=https://dl.fedoraproject.org/pub/eln/1/Extras/source/tree/
metalink=https://mirrors.fedoraproject.org/metalink?repo=eln-extras-source-1&arch=$basearch
enabled=0
metadata_expire=6h
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-fedora-eln-$basearch
skip_if_unavailable=False



[eln-ha]
name=Fedora - ELN HighAvailability - Developmental packages for the next Enterprise Linux release
#baseurl=https://dl.fedoraproject.org/pub/eln/1/HighAvailability/$basearch/os/
metalink=https://mirrors.fedoraproject.org/metalink?repo=eln-highavailability-1&arch=$basearch
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
#baseurl=https://dl.fedoraproject.org/pub/eln/1/HighAvailability/$basearch/debug/tree
metalink=https://mirrors.fedoraproject.org/metalink?repo=eln-highavailability-debug-1&arch=$basearch
enabled=0
metadata_expire=6h
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-fedora-eln-$basearch
skip_if_unavailable=False

[eln-ha-source]
name=Fedora - ELN HighAvailability - Source
#baseurl=https://dl.fedoraproject.org/pub/eln/1/HighAvailability/source/tree/
metalink=https://mirrors.fedoraproject.org/metalink?repo=eln-highavailability-source-1&arch=source
enabled=0
metadata_expire=6h
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-fedora-eln-$basearch
skip_if_unavailable=False



[eln-rt]
name=Fedora - ELN RT - Developmental packages for the next Enterprise Linux release
#baseurl=https://dl.fedoraproject.org/pub/eln/1/RT/$basearch/os/
metalink=https://mirrors.fedoraproject.org/metalink?repo=eln-rt-1&arch=$basearch
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
#baseurl=https://dl.fedoraproject.org/pub/eln/1/RT/$basearch/debug/tree
metalink=https://mirrors.fedoraproject.org/metalink?repo=eln-rt-debug-1&arch=$basearch
enabled=0
metadata_expire=6h
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-fedora-eln-$basearch
skip_if_unavailable=False

[eln-rt-source]
name=Fedora - ELN RT - Source
#baseurl=https://dl.fedoraproject.org/pub/eln/1/RT/source/tree/
metalink=https://mirrors.fedoraproject.org/metalink?repo=eln-rt-source-1&arch=source
enabled=0
metadata_expire=6h
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-fedora-eln-$basearch
skip_if_unavailable=False



[eln-nfv]
name=Fedora - ELN NFV - Developmental packages for the next Enterprise Linux release
#baseurl=https://dl.fedoraproject.org/pub/eln/1/NFV/$basearch/os/
metalink=https://mirrors.fedoraproject.org/metalink?repo=eln-nfv-1&arch=$basearch
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
#baseurl=https://dl.fedoraproject.org/pub/eln/1/NFV/$basearch/debug/tree
metalink=https://mirrors.fedoraproject.org/metalink?repo=eln-nfv-debug-1&arch=$basearch
enabled=0
metadata_expire=6h
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-fedora-eln-$basearch
skip_if_unavailable=False

[eln-nfv-source]
name=Fedora - ELN NFV - Source
#baseurl=https://dl.fedoraproject.org/pub/eln/1/NFV/source/tree/
metalink=https://mirrors.fedoraproject.org/metalink?repo=eln-nfv-source-1&arch=source
enabled=0
metadata_expire=6h
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-fedora-eln-$basearch
skip_if_unavailable=False



[eln-sap]
name=Fedora - ELN SAP - Developmental packages for the next Enterprise Linux release
#baseurl=https://dl.fedoraproject.org/pub/eln/1/SAP/$basearch/os/
metalink=https://mirrors.fedoraproject.org/metalink?repo=eln-sap-1&arch=$basearch
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
#baseurl=https://dl.fedoraproject.org/pub/eln/1/SAP/$basearch/debug/tree
metalink=https://mirrors.fedoraproject.org/metalink?repo=eln-sap-debug-1&arch=$basearch
enabled=0
metadata_expire=6h
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-fedora-eln-$basearch
skip_if_unavailable=False

[eln-sap-source]
name=Fedora - ELN SAP - Source
#baseurl=https://dl.fedoraproject.org/pub/eln/1/SAP/source/tree/
metalink=https://mirrors.fedoraproject.org/metalink?repo=eln-sap-source-1&arch=$basearch
enabled=0
metadata_expire=6h
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-fedora-eln-$basearch
skip_if_unavailable=False



[eln-saphana]
name=Fedora - ELN SAPHANA - Developmental packages for the next Enterprise Linux release
#baseurl=https://dl.fedoraproject.org/pub/eln/1/SAPHANA/$basearch/os/
metalink=https://mirrors.fedoraproject.org/metalink?repo=eln-saphana-1&arch=$basearch
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
#baseurl=https://dl.fedoraproject.org/pub/eln/1/SAPHANA/$basearch/debug/tree
metalink=https://mirrors.fedoraproject.org/metalink?repo=eln-saphana-debug-1&arch=$basearch
enabled=0
metadata_expire=6h
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-fedora-eln-$basearch
skip_if_unavailable=False

[eln-saphana-source]
name=Fedora - ELN SAPHANA - Source
#baseurl=https://dl.fedoraproject.org/pub/eln/1/SAPHANA/source/tree/
metalink=https://mirrors.fedoraproject.org/metalink?repo=eln-saphana-source-1&arch=source
enabled=0
metadata_expire=6h
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-fedora-eln-$basearch
skip_if_unavailable=False

[local]
name=local
baseurl=https://kojipkgs.fedoraproject.org/repos/eln-build/latest/$basearch/
cost=2000
enabled=0
skip_if_unavailable=False
"""
