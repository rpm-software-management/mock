#!/bin/sh

if test -z "$TESTDIR"; then
    TESTDIR=$(dirname "$(readlink -f "$0")")
fi

. "${TESTDIR}/functions"
set -e

TMPDIR=$(mktemp -d)
cleanup() { rm -rf "$TMPDIR"; }
trap cleanup EXIT

header "mock with --rootdir option"

for isolation in simple nspawn; do
    runcmd "$MOCKCMD --isolation=$isolation --rootdir=$TMPDIR --scrub=chroot"
    runcmd "$MOCKCMD --isolation=$isolation --rootdir=$TMPDIR --scrub=bootstrap"
    runcmd "$MOCKCMD --isolation=$isolation --rootdir=$TMPDIR --bootstrap-chroot ${TESTDIR}/test-C-1.1-0.src.rpm"
done
