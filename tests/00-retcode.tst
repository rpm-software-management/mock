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

header "testing exit code on unsupported command line"
runcmd "$MOCKCMD --offline --scm-enable --scm-option method=unsupported"
res=$?
if [ $res -ne 5 ]; then
    echo "mock pass exit code $res instead of 5 where there is problem with command line options"
    exit 1
fi

header "testing that error in root.log is passed back correctly"
runcmd "$MOCKCMD --offline --rebuild ${TESTDIR}/test-E-1.1-0.src.rpm"
res=$?
if [ $res -ne 30 ]; then
    echo "mock pass exit code $res instead of 30 where there is problem in root.log"
    exit 1
fi

header "testing error code when resultdir cannot be created"
runcmd "$MOCKCMD --offline --resultdir=/proc/doesnotwork --rebuild ${TESTDIR}/test-C-1.1-0.src.rpm"
res=$?
if [ $res -ne 70 ]; then
    echo "mock pass exit code $res instead of 70 when resultdir cannot be created"
    exit 1
fi
