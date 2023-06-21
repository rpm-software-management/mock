config_opts['chroot_setup_cmd'] = 'install bash bzip2 coreutils cpio diffutils redhat-release findutils gawk glibc-minimal-langpack grep gzip info patch redhat-rpm-config rpm-build sed shadow-utils tar unzip util-linux which xz'
config_opts['releasever'] = '9'
config_opts['dist'] = 'el{{ releasever }}'  # only useful for --resultdir variable subst
config_opts['extra_chroot_dirs'] = [ '/run/lock', ]
config_opts['package_manager'] = 'dnf'
config_opts['bootstrap_image'] = 'registry.access.redhat.com/ubi{{ releasever }}/ubi'
config_opts['bootstrap_image_ready'] = True
config_opts['description'] = 'RHEL {{ releasever }}'

config_opts['dnf_install_command'] += ' subscription-manager'
config_opts['yum_install_command'] += ' subscription-manager'

config_opts['root'] = 'rhel-{{ releasever }}-{{ target_arch }}'

config_opts['redhat_subscription_required'] = True

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
module_platform_id=platform:el{{ releasever }}
protected_packages=
user_agent={{ user_agent }}

# repos
[baseos]
name = Red Hat Enterprise Linux - BaseOS
baseurl = https://cdn.redhat.com/content/dist/rhel9/$releasever/$basearch/baseos/os/
sslverify = 1
sslcacert = /etc/rhsm/ca/redhat-uep.pem
sslclientkey = /etc/pki/entitlement/{{ redhat_subscription_key_id }}-key.pem
sslclientcert = /etc/pki/entitlement/{{ redhat_subscription_key_id }}.pem
gpgkey = file:///usr/share/distribution-gpg-keys/redhat/RPM-GPG-KEY-redhat{{ releasever }}-release
skip_if_unavailable=False

[appstream]
name = Red Hat Enterprise Linux - AppStream
baseurl = https://cdn.redhat.com/content/dist/rhel9/$releasever/$basearch/appstream/os/
sslverify = 1
sslcacert = /etc/rhsm/ca/redhat-uep.pem
sslclientkey = /etc/pki/entitlement/{{ redhat_subscription_key_id }}-key.pem
sslclientcert = /etc/pki/entitlement/{{ redhat_subscription_key_id }}.pem
gpgkey = file:///usr/share/distribution-gpg-keys/redhat/RPM-GPG-KEY-redhat{{ releasever }}-release
skip_if_unavailable=False

[codeready-builder]
name = Red Hat Enterprise Linux - CodeReady Linux Builder
baseurl = https://cdn.redhat.com/content/dist/rhel9/$releasever/$basearch/codeready-builder/os/
sslverify = 1
sslcacert = /etc/rhsm/ca/redhat-uep.pem
sslclientkey = /etc/pki/entitlement/{{ redhat_subscription_key_id }}-key.pem
sslclientcert = /etc/pki/entitlement/{{ redhat_subscription_key_id }}.pem
gpgkey = file:///usr/share/distribution-gpg-keys/redhat/RPM-GPG-KEY-redhat{{ releasever }}-release
skip_if_unavailable=False
"""
