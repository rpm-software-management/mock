#!/usr/bin/bash
# This script is invoked when container is created without network.
# It will set default route to localhost so multicast work.

# uuid of the container, you can obtain it from `machinectl list`
container=$1

# setup
mkdir -p /run/netns
eval $(machinectl show -p Leader ${container})
touch /run/netns/ns-pid-${Leader}
mount --bind /proc/${Leader}/ns/net /run/netns/ns-pid-${Leader}

# add route
ip netns exec ns-pid-${Leader} ip route add default via 127.0.0.1

# clean up
umount /run/netns/ns-pid-${Leader}
rm -f /run/netns/ns-pid-${Leader}
