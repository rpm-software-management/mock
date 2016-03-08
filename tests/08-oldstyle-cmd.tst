#!/bin/sh

. ${TESTDIR}/functions

#
# test old-style cmdline options
#
header "test old-style cmdline options"
runcmd "$MOCKCMD --offline clean"
runcmd "$MOCKCMD --offline init"
runcmd "$MOCKCMD --disable-plugin=tmpfs install ccache"
if [ ! -e $CHROOT/usr/bin/ccache ]; then
    echo "init/clean test FAILED. ccache not found."
    exit 1
fi

