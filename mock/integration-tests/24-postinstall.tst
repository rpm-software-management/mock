#!/bin/sh

if test -z "$TESTDIR"; then
    TESTDIR=$(dirname "$(readlink -f "$0")")
fi

. "${TESTDIR}/functions"
set -e

: "${MOCKCMD=mock}"

header "mock --rebuild --postinstall test"

TMPDIR=$(mktemp -d)
cleanup() { rm -rf "$TMPDIR"; }
trap cleanup EXIT

for isolation in simple nspawn; do
    for bootstrap in no-bootstrap-chroot bootstrap-chroot; do
        mock="$MOCKCMD --isolation=$isolation --$bootstrap"
        : "${TESTSRPM=$TESTDIR/test-C-1.1-0.src.rpm}"
        $mock --rebuild "$TESTSRPM" --postinstall --no-cleanup-after
        $mock --shell 'rpm -qa' | grep test-C
        $mock --scrub=chroot
        $mock --scrub=bootstrap
    done
done
exit 0
