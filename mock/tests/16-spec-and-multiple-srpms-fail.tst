#!/bin/sh

. ${TESTDIR}/functions

header "test --spec with multiple srpms failure"
runcmd "$MOCKCMD --spec ${TESTDIR}/test-C.spec ${TESTDIR}/test-C-1.1-0.src.rpm ${TESTDIR}/test-B-1.1-0.src.rpm"
res=$?

if [ $res -ne 50 ]; then
   echo "mock returned success when it should have failed!"
   exit 1
fi
exit 0
