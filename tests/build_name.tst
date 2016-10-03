#!/bin/sh

. ${TESTDIR}/functions

header "Build name"
runcmd "$MOCKCMD --offline -D '%build_name.tst foobar' ${TESTDIR}/test-C-1.1-0.src.rpm"
res=$?

if [ $res -ne 0 ]; then
   test = rpm -qip --queryformat "%{BUILDHOST}"
   if grep -iR "foobar" test <> 0 then
   echo "Success" 
   exit 1
fi
echo "Fail"
exit 0


