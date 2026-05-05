#!/bin/sh

. ${TESTDIR}/functions

header "Test nspawn_host_dev: loop partition devices visible"
runcmd "$MOCKCMD --isolation=nspawn --no-bootstrap-image \
    --config-opts=nspawn_host_dev=True \
    --install util-linux \
    --shell '
        truncate -s 100M /tmp/test.img &&
        dev=\$(losetup -fP --show /tmp/test.img) &&
        echo \",,L\" | sfdisk \$dev &&  # create one Linux partition spanning the whole disk
        test -b \${dev}p1 &&
        echo HOST_DEV_OK;
        losetup -d \$dev;
        rm -f /tmp/test.img
    '" || die "nspawn_host_dev: loop partition device not visible"
