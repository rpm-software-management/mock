#!/bin/sh

. ${TESTDIR}/functions

#
# Test orphanskill feature (std)
#
header "Test orphanskill feature (std)"
if pgrep daemontest; then
    echo "Exiting because there is already a daemontest running."
    exit 1
fi
runcmd "$MOCKCMD --offline --init"
runcmd "$MOCKCMD --offline --copyin tests/daemontest.c /tmp"
runcmd "$MOCKCMD --offline --chroot -- gcc -Wall -o /tmp/daemontest /tmp/daemontest.c"
runcmd "$MOCKCMD --offline --chroot -- /tmp/daemontest"
if pgrep daemontest; then
    echo "Daemontest FAILED. found a daemontest process running after exit." 
    exit 1
fi

