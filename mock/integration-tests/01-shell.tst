#!/bin/sh

. ${TESTDIR}/functions

#
# test mock shell (interactive) and return code passing
#
header "testing interactive shell and return code"
echo exit 5 | runcmd "$MOCKCMD --old-chroot --offline --shell"
res=$?
if [ $res -ne 5 ]; then
    echo "'mock --chroot' return code not properly passed back: $res"
    exit 1
fi
