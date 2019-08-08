#!/bin/sh

. ${TESTDIR}/functions

header "test mockchain partial failure"
runcmd "$MOCKCHAIN --offline -c ${TESTDIR}/*.src.rpm"
res=$?

if [ $res -ne 4 ]; then
   echo "mockchain did not report partial failure when it should!"
   exit 1
fi
exit 0
