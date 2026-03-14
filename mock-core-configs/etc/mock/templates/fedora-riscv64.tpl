config_opts['root'] = 'fedora-{{ releasever }}-{{ target_arch }}'

config_opts['description'] = 'Fedora {{ releasever }} RISC-V'
config_opts['chroot_setup_cmd'] = 'install @build'

config_opts['dist'] = 'fc{{ releasever }}'
config_opts['extra_chroot_dirs'] = [ '/run/lock', ]

config_opts['package_manager'] = 'dnf5'

config_opts['use_bootstrap'] = False

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
protected_packages=
user_agent={{ user_agent }}

# repos

[local]
name=local
baseurl=https://riscv-koji.fedoraproject.org/repos/f{{ releasever }}-build/latest/riscv64/
gpgcheck=0
enabled=1
skip_if_unavailable=False

[fedora]
name=fedora
baseurl=https://riscv-koji.fedoraproject.org/repos-dist/f{{ releasever }}/latest/riscv64/
gpgcheck=0
enabled=1
skip_if_unavailable=False
"""
