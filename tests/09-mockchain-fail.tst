#!/bin/sh

. ${TESTDIR}/functions

header "test mockchain failure"
runcmd "$MOCKCHAIN ${TESTDIR}/*.src.rpm"
res=$?

if [ $res -eq 0 ]; then
   echo "mockchain returned success when it should have failed!"
   exit 1
fi
exit 0
