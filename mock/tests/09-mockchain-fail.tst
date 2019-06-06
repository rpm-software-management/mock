#!/bin/sh

. ${TESTDIR}/functions

header "test mockchain failure"
runcmd "$MOCKCHAIN --offline ${TESTDIR}/test-A-1.1-0.src.rpm ${TESTDIR}/test-B-1.1-0.src.rpm"
res=$?

if [ $res -eq 0 ]; then
   echo "mockchain returned success when it should have failed!"
   exit 1
fi
exit 0
