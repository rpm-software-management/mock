config_opts['chroot_setup_cmd'] = 'install bash bzip2 coreutils cpio diffutils findutils gawk glibc-minimal-langpack grep gzip info patch redhat-release redhat-rpm-config rpm-build sed shadow-utils tar unzip util-linux which xz'
config_opts['releasever'] = '10'
config_opts['releasever_major'] = '10'
config_opts['dist'] = 'el{{ releasever_major }}'  # only useful for --resultdir variable subst
config_opts['extra_chroot_dirs'] = [ '/run/lock', ]
config_opts['package_manager'] = 'dnf'
config_opts['bootstrap_image'] = 'registry.access.redhat.com/ubi{{ releasever_major }}/ubi'
config_opts['bootstrap_image_ready'] = True
config_opts['description'] = 'RHEL {{ releasever_major }}'

config_opts['dnf_install_command'] += ' subscription-manager'
config_opts['yum_install_command'] += ' subscription-manager'

config_opts['root'] = 'rhel-{{ releasever_major }}-{{ target_arch }}'

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
protected_packages=
skip_if_unavailable=False
user_agent={{ user_agent }}

[baseos]
name=Red Hat Enterprise Linux {{ releasever_major }} for {{ target_arch }} - BaseOS (RPMs)
baseurl=https://cdn.redhat.com/content/dist/rhel{{ releasever_major }}/{{ releasever }}/{{ target_arch }}/baseos/os/
sslverify=1
sslcacert=/etc/rhsm/ca/redhat-uep.pem
sslclientkey=/etc/pki/entitlement/{{ redhat_subscription_key_id }}-key.pem
sslclientcert=/etc/pki/entitlement/{{ redhat_subscription_key_id }}.pem
gpgkey=file:///usr/share/distribution-gpg-keys/redhat/RPM-GPG-KEY-redhat{{ releasever_major }}-release

[appstream]
name=Red Hat Enterprise Linux {{ releasever_major }} for {{ target_arch }} - AppStream (RPMs)
baseurl=https://cdn.redhat.com/content/dist/rhel{{ releasever_major }}/{{ releasever }}/{{ target_arch }}/appstream/os/
sslverify=1
sslcacert=/etc/rhsm/ca/redhat-uep.pem
sslclientkey=/etc/pki/entitlement/{{ redhat_subscription_key_id }}-key.pem
sslclientcert=/etc/pki/entitlement/{{ redhat_subscription_key_id }}.pem
gpgkey=file:///usr/share/distribution-gpg-keys/redhat/RPM-GPG-KEY-redhat{{ releasever_major }}-release

[crb]
name=Red Hat CodeReady Linux Builder for RHEL {{ releasever_major }} {{ target_arch }} (RPMs)
baseurl=https://cdn.redhat.com/content/dist/rhel{{ releasever_major }}/{{ releasever }}/{{ target_arch }}/codeready-builder/os/
sslverify=1
sslcacert=/etc/rhsm/ca/redhat-uep.pem
sslclientkey=/etc/pki/entitlement/{{ redhat_subscription_key_id }}-key.pem
sslclientcert=/etc/pki/entitlement/{{ redhat_subscription_key_id }}.pem
gpgkey=file:///usr/share/distribution-gpg-keys/redhat/RPM-GPG-KEY-redhat{{ releasever_major }}-release

[highavailability]
name=Red Hat Enterprise Linux {{ releasever_major }} for {{ target_arch }} - High Availability (RPMs)
baseurl=https://cdn.redhat.com/content/dist/rhel{{ releasever_major }}/{{ releasever }}/{{ target_arch }}/highavailability/os/
sslverify=1
sslcacert=/etc/rhsm/ca/redhat-uep.pem
sslclientkey=/etc/pki/entitlement/{{ redhat_subscription_key_id }}-key.pem
sslclientcert=/etc/pki/entitlement/{{ redhat_subscription_key_id }}.pem
gpgkey=file:///usr/share/distribution-gpg-keys/redhat/RPM-GPG-KEY-redhat{{ releasever_major }}-release
enabled=0

[nfv]
name=Red Hat Enterprise Linux {{ releasever_major }} for {{ target_arch }} - Real Time for NFV (RPMs)
baseurl=https://cdn.redhat.com/content/dist/rhel{{ releasever_major }}/{{ releasever }}/{{ target_arch }}/nfv/os/
sslverify=1
sslcacert=/etc/rhsm/ca/redhat-uep.pem
sslclientkey=/etc/pki/entitlement/{{ redhat_subscription_key_id }}-key.pem
sslclientcert=/etc/pki/entitlement/{{ redhat_subscription_key_id }}.pem
gpgkey=file:///usr/share/distribution-gpg-keys/redhat/RPM-GPG-KEY-redhat{{ releasever_major }}-release
enabled=0

[rt]
name=Red Hat Enterprise Linux {{ releasever_major }} for {{ target_arch }} - Real Time (RPMs)
baseurl=https://cdn.redhat.com/content/dist/rhel{{ releasever_major }}/{{ releasever }}/{{ target_arch }}/rt/os/
sslverify=1
sslcacert=/etc/rhsm/ca/redhat-uep.pem
sslclientkey=/etc/pki/entitlement/{{ redhat_subscription_key_id }}-key.pem
sslclientcert=/etc/pki/entitlement/{{ redhat_subscription_key_id }}.pem
gpgkey=file:///usr/share/distribution-gpg-keys/redhat/RPM-GPG-KEY-redhat{{ releasever_major }}-release
enabled=0

"""
