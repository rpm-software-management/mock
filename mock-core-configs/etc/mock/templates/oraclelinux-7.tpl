# This list is taken from 'epel-7-x86_64' @buildsys-build group, minus the
# 'epel-*' specific stuff.
config_opts['chroot_setup_cmd'] = 'install bash bzip2 coreutils cpio diffutils findutils gawk gcc gcc-c++ grep gzip info make oraclelinux-release patch redhat-rpm-config rpm-build sed shadow-utils tar unzip util-linux which xz'

config_opts['dist'] = 'el7'  # only useful for --resultdir variable subst
config_opts['releasever'] = '7'
config_opts['bootstrap_image'] = 'docker.io/library/oraclelinux:7'
config_opts['package_manager'] = 'yum'

config_opts['yum_install_command'] += " --disablerepo=ol7_software_collections"

config_opts['yum.conf'] = """
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
protected_packages=
user_agent={{ user_agent }}

# repos

[ol7_latest]
name=Oracle Linux $releasever Latest ($basearch)
baseurl=https://yum.oracle.com/repo/OracleLinux/OL7/latest/$basearch/
gpgkey=file:///usr/share/distribution-gpg-keys/oraclelinux/RPM-GPG-KEY-oracle-ol7
gpgcheck=1
enabled=1
skip_if_unavailable=False

[ol7_optional_latest]
name=Oracle Linux $releasever Optional Latest ($basearch)
baseurl=https://yum.oracle.com/repo/OracleLinux/OL7/optional/latest/$basearch/
gpgkey=file:///usr/share/distribution-gpg-keys/oraclelinux/RPM-GPG-KEY-oracle-ol7
gpgcheck=1
enabled=1
skip_if_unavailable=False

[ol7_software_collections]
name=Software Collection Library packages for Oracle Linux 7 ($basearch)
baseurl=https://yum.oracle.com/repo/OracleLinux/OL7/SoftwareCollections/$basearch/
gpgkey=file:///usr/share/distribution-gpg-keys/oraclelinux/RPM-GPG-KEY-oracle-ol7
gpgcheck=1
enabled=1
includepkgs=devtoolset*
skip_if_unavailable=False

{% for uekver in range(3,7) %}
[ol7_UEKR{{ uekver }}]
name=Latest Unbreakable Enterprise Kernel Release {{ uekver }} for Oracle Linux $releasever ($basearch)
baseurl=https://yum.oracle.com/repo/OracleLinux/OL7/UEKR{{ uekver }}/$basearch/
gpgkey=file:///usr/share/distribution-gpg-keys/oraclelinux/RPM-GPG-KEY-oracle-ol7
gpgcheck=1
enabled=0
{% endfor %}

"""
