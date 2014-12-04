#!/bin/sh

. ${TESTDIR}/functions

header "test mockchain success"
TMPDIR=$(mktemp -d)
runcmd "$MOCKCMD ${TESTDIR}/test-C-1.1-0.src.rpm ${TESTDIR}/test-D-1.1-0.src.rpm --resultdir $TMPDIR"
res=$?

if [ $res -ne 0 ]; then
   echo "mock returned fail when should have succeeded!"
   exit 1
fi
exit 0
