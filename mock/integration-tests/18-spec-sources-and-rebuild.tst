#!/bin/sh

. ${TESTDIR}/functions

header "test --spec and --sources arguments with rebuild"
runcmd "$MOCKCMD --spec ${TESTDIR}/test-C.spec --sources ${TESTDIR}/"
res=$?

if [ $res -ne 0 ]; then
   echo "mock rebuild failed"
   exit 1
fi
exit 0
