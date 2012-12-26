#!/bin/sh

. ${TESTDIR}/functions

#
# Test that chroot return code is properly passed up
#

header "testing that chroot return code is passed back correctly"
runcmd "$MOCKCMD --offline --chroot -- bash -c 'exit 5'"
res=$?
if [ $res -ne 5 ]; then
    echo "'mock --chroot' return code not properly passed back: $res"
    exit 1
fi
