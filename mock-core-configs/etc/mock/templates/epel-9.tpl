config_opts['chroot_setup_cmd'] += " epel-rpm-macros"

# epel9-next is launching before epel9.  This file will not have repo
# definitions until after the epel9 launch.
