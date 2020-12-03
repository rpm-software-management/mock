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

daemon_package=https://github.com/rpm-software-management/mock-test-data/raw/main/daemontest-1-0.src.rpm

for isolation in nspawn simple; do
    for bootstrap in --bootstrap-chroot --no-bootstrap-chroot; do
        selector="--isolation=$isolation $bootstrap"
        mock="$MOCKCMD_NO_RESULTDIR $selector"

        tmpdir=/var/tmp

        runcmd "$mock --offline --init"
        runcmd "$mock --install gcc"
        runcmd "$mock --offline --copyin integration-tests/daemontest.c $tmpdir"
        runcmd "$mock --offline --chroot -- gcc -Wall -o $tmpdir/daemontest $tmpdir/daemontest.c"

        runcmd "$mock --offline --chroot -- $tmpdir/daemontest"
        pgrep daemontest && die "Daemontest FAILED. found a daemontest process running after exit ($selector)."

        runcmd "$mock --chain $daemon_package" \
            || die "Can't build daemon package ($selector)."

        pgrep daemontest && die "Leftover daemontest process ($selector)."

        runcmd "$mock --chain $daemon_package --postinstall --config-opts=cleanup_on_success=False" \
            || die "Can't build && install the daemon package ($selector)."

        pgrep daemontest && die "Leftover daemontest process after --postinstall ($selector)."

        runcmd "$mock --shell 'set -x; /usr/bin/daemontest ; sleep 60 ;'" &
        mockchild=$!
        sleep 10 # give mock some time to start the daemontest process

        pgrep daemontest || die "The daemontest process doesn't exit ($selector)."
        runcmd "$mock --orphanskill"

        wait "$mockchild" && "Unexpected success of mock ($selector)."

        pgrep daemontest && die "The daemontest should be killed ($selector)."

        # "uninstall" the $rpm from chroot
        runcmd "$MOCKCMD --scrub chroot" || die "Can't scrub ($selector).".
    done
done

exit 0
