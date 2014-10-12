#!/bin/sh

. ${TESTDIR}/functions

#
# Test orphanskill feature (explicit)
#
header "Test orphanskill feature (explicit)"
runcmd "$MOCKCMD --offline --init"
runcmd "$MOCKCMD --offline --copyin tests/daemontest.c /tmp"
runcmd "$MOCKCMD --offline --chroot -- gcc -Wall -o /tmp/daemontest /tmp/daemontest.c"
echo -e '#!/bin/sh\n/tmp/daemontest\nsleep 60\n' >> $CHROOT/tmp/try
# the following should launch about three processes in the chroot: bash, sleep, daemontest
$MOCKCMD --offline --chroot -- bash /tmp/try &
sleep 10
mockpid=$!
sleep 1
# now we 'prematurely' kill mock. This should leave the three orphans above
sudo kill -9 $mockpid
if ! pgrep daemontest; then
    echo "Daemontest failed. daemontest should be running now but is not."
    exit 1
fi
$MOCKCMD --offline --orphanskill 
if pgrep daemontest; then
    echo "Daemontest FAILED. found a daemontest process running after exit." 
    exit 1
fi
