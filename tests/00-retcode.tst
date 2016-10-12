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

header "testing that error in root.log is passed back correctly"
runcmd "$MOCKCMD --offline --rebuild ${TESTDIR}/test-E-1.1-0.src.rpm"
res=$?
if [ $res -ne 30 ]; then
    echo "'mock pass exit code $res instead of 30 where there is problem in root.log"
    exit 1
fi
