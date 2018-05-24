#!/bin/sh

. ${TESTDIR}/functions

header "test --spec with multiple srpms failure"
runcmd "$MOCK --spec ${TESTDIR}/test-A.spec ${TESTDIR}/test-A-1.1-0.src.rpm ${TESTDIR}/test-B-1.1-0.src.rpm"
res=$?

if [ $res -ne 50 ]; then
   echo "mock returned success when it should have failed!"
   exit 1
fi
exit 0
