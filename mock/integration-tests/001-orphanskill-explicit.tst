#!/bin/sh

. ${TESTDIR}/functions

#
# Test orphanskill feature (explicit)
#
header "Test orphanskill feature (explicit)"

tmpdir=/var/tmp

runcmd "$MOCKCMD --offline --init"
runcmd "$MOCKCMD --install gcc"
runcmd "$MOCKCMD --offline --disable-plugin=tmpfs --copyin integration-tests/daemontest.c $tmpdir"
runcmd "$MOCKCMD --offline --disable-plugin=tmpfs --chroot -- gcc -Wall -o $tmpdir/daemontest $tmpdir/daemontest.c"

echo "#!/bin/sh
set -x
$tmpdir/daemontest
sleep 60" >> "$CHROOT$tmpdir/try"

for isolation in simple nspawn; do
    for bootstrap in --bootstrap-chroot --no-bootstrap-chroot; do
        selector="--isolation=$isolation $bootstrap"

        # the following should launch about three processes in the chroot: bash,
        # sleep, daemontest
        runcmd "$MOCKCMD $selector --offline --disable-plugin=tmpfs --chroot -- bash $tmpdir/try" &
        mockpid=$!
        sleep 10

        ! test -d /proc/$mockpid && die "Mock stopped too early ($selector)."
        ! pgrep daemontest && die "Daemontest failed. daemontest should be running now but is not ($selector)."

        runcmd "$MOCKCMD $selector --offline --disable-plugin=tmpfs --orphanskill"

        wait "$mockpid" && "Unexpected success of mock ($selector)."

        pgrep daemontest && die "Daemontest FAILED. found a daemontest process running after exit ($selector)."
    done
done

exit 0
