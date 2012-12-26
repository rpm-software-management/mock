#!/bin/sh

. ${TESTDIR}/functions

#
# test init/clean
#
header "test init/clean"
runcmd "$MOCKCMD --offline --clean"
if [ -e $CHROOT ]; then
    echo "clean test FAILED. still found $CHROOT dir."
    exit 1
fi

runcmd "$MOCKCMD --offline --init"
runcmd "$MOCKCMD --offline --install ccache"
if [ ! -e $CHROOT/usr/bin/ccache ]; then
    echo "init/clean test FAILED. ccache not found."
    exit 1
fi

