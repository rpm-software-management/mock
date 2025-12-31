include('eol/templates/centos-6.tpl')

# Copy the ca-bundle file from the host.  This is unnecessary for EL7+ chroots
# because the bundle is a symlink to
# /etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem, and the /etc/pki/ca-trust
# directory is already copied from the host via
# config_opts['ssl_copied_ca_trust_dirs'].
config_opts['ssl_ca_bundle_path'] = '/etc/pki/tls/certs/ca-bundle.crt'

config_opts['chroot_setup_cmd'] = 'install @buildsys-build'

config_opts['yum.conf'] += """
[epel]
name=Extra Packages for Enterprise Linux $releasever - $basearch
mirrorlist=http://mirrors.fedoraproject.org/mirrorlist?repo=epel-6&arch=$basearch
failovermethod=priority
gpgkey=file:///usr/share/distribution-gpg-keys/epel/RPM-GPG-KEY-EPEL-6
gpgcheck=1
skip_if_unavailable=False

[epel-testing]
name=Extra Packages for Enterprise Linux $releasever - Testing - $basearch
enabled=0
mirrorlist=http://mirrors.fedoraproject.org/mirrorlist?repo=testing-epel6&arch=$basearch
failovermethod=priority
skip_if_unavailable=False

[local]
name=local
baseurl=https://kojipkgs.fedoraproject.org/repos/dist-6E-epel-build/latest/$basearch/
cost=2000
enabled=0
skip_if_unavailable=False

[epel-debuginfo]
name=Extra Packages for Enterprise Linux $releasever - $basearch - Debug
mirrorlist=http://mirrors.fedoraproject.org/mirrorlist?repo=epel-debug-6&arch=$basearch
failovermethod=priority
enabled=0
skip_if_unavailable=False
"""
