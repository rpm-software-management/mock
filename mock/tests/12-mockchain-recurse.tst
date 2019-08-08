#!/bin/sh

. ${TESTDIR}/functions

header "test mockchain recursive success"
runcmd "$MOCKCHAIN --recurse ${TESTDIR}/test-A-1.1-0.src.rpm ${TESTDIR}/test-B-1.1-0.src.rpm ${TESTDIR}/test-C-1.1-0.src.rpm"
res=$?

if [ $res -ne 0 ]; then
   echo "mockchain returned fail when should have succeeded!"
   exit 1
fi
exit 0
