# This list is taken from 'epel-6-x86_64' @buildsys-build group, minus the
# 'epel-*' specific stuff.
config_opts['chroot_setup_cmd'] = 'install bash bzip2 coreutils cpio diffutils findutils gawk gcc gcc-c++ grep gzip info make patch redhat-rpm-config rpm-build sed shadow-utils tar unzip util-linux-ng which xz'

config_opts['dist'] = 'el6'  # only useful for --resultdir variable subst
# beware RHEL uses 6Server or 6Client
config_opts['releasever'] = '6'
config_opts['isolation'] = 'simple'
config_opts['bootstrap_image'] = 'registry.access.redhat.com/rhel6'
config_opts['package_manager'] = 'yum'

config_opts['dnf_install_command'] += ' subscription-manager'
config_opts['yum_install_command'] += ' subscription-manager'

config_opts['redhat_subscription_required'] = True
config_opts['rhel_product'] = '6Server'

config_opts['yum.conf'] = """
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
metadata_expire=0
mdpolicy=group:primary
best=1
protected_packages=
user_agent={{ user_agent }}

# repos
[base]
name=Red Hat Enterprise Linux
enabled=1
baseurl=https://cdn.redhat.com/content/dist/rhel/server/6/{{ rhel_product }}/$basearch/os
failovermethod=priority
ui_repoid_vars = releasever basearch
gpgkey=file:///usr/share/distribution-gpg-keys/redhat/RPM-GPG-KEY-redhat6-release
skip_if_unavailable=False
sslcacert = /etc/rhsm/ca/redhat-uep.pem
sslclientkey = /etc/pki/entitlement/{{ redhat_subscription_key_id }}-key.pem
sslclientcert = /etc/pki/entitlement/{{ redhat_subscription_key_id }}.pem

[rhel-optional]
name = Red Hat Enterprise Linux - Optional
baseurl = https://cdn.redhat.com/content/dist/rhel/server/6/{{ rhel_product }}/$basearch/optional/os
failovermethod=priority
gpgkey=file:///usr/share/distribution-gpg-keys/redhat/RPM-GPG-KEY-redhat6-release
skip_if_unavailable=False
ui_repoid_vars = releasever basearch
sslcacert = /etc/rhsm/ca/redhat-uep.pem
sslclientkey = /etc/pki/entitlement/{{ redhat_subscription_key_id }}-key.pem
sslclientcert = /etc/pki/entitlement/{{ redhat_subscription_key_id }}.pem

[extras]
name = Red Hat Enterprise Linux - Extras
baseurl = https://cdn.redhat.com/content/dist/rhel/server/6/{{ rhel_product }}/$basearch/extras/os
failovermethod=priority
gpgkey=file:///usr/share/distribution-gpg-keys/redhat/RPM-GPG-KEY-redhat6-release
skip_if_unavailable=False
ui_repoid_vars = releasever basearch
sslcacert = /etc/rhsm/ca/redhat-uep.pem
sslclientkey = /etc/pki/entitlement/{{ redhat_subscription_key_id }}-key.pem
sslclientcert = /etc/pki/entitlement/{{ redhat_subscription_key_id }}.pem
"""
