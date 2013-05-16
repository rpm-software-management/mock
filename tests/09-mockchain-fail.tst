#!/bin/sh

. ${TESTDIR}/functions

header "test mockchain failure"
runcmd "$MOCKCHAIN ${TESTDIR}/*.src.rpm"
res=$?

if [ $res -ne 1 ]; then
   echo "mockchain returned sucess when should have failed!"
   exit 1
fi
exit 0
