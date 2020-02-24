#!/bin/sh

. ${TESTDIR}/functions

#
# Test orphanskill feature (explicit)
#
header "Test orphanskill feature (explicit)"
runcmd "$MOCKCMD --offline --init"
runcmd "$MOCKCMD --offline --disable-plugin=tmpfs --copyin tests/daemontest.c /tmp"
runcmd "$MOCKCMD --offline --disable-plugin=tmpfs --chroot -- gcc -Wall -o /tmp/daemontest /tmp/daemontest.c"
# ask for sudo password, so later we do not need to wait for password, because the second sudo need to be
# executed within 10 seconds
sudo echo init sudo
echo -e '#!/bin/sh\n/tmp/daemontest\nsleep 60\n' >> $CHROOT/tmp/try
# the following should launch about three processes in the chroot: bash, sleep, daemontest
$MOCKCMD --offline --disable-plugin=tmpfs --chroot -- bash /tmp/try &
sleep 10
mockpid=$!
sleep 1
# now we 'prematurely' kill mock. This should leave the three orphans above
sudo kill -9 $mockpid
sleep 1
if ! pgrep daemontest; then
    echo "Daemontest failed. daemontest should be running now but is not."
    exit 1
fi
$MOCKCMD --offline --disable-plugin=tmpfs --orphanskill
if pgrep daemontest; then
    echo "Daemontest FAILED. found a daemontest process running after exit." 
    exit 1
fi
