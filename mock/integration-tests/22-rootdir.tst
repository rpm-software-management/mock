#!/bin/sh

if test -z "$TESTDIR"; then
    TESTDIR=$(dirname "$(readlink -f "$0")")
fi

. "${TESTDIR}/functions"
set -e

# creating special files (e.g. /dev/null doesn't work below tmpfs)
WORKDIR=$(mktemp -d -p "$HOME")

cleanup() { rm -rf "$WORKDIR"; }
trap cleanup EXIT

header "mock with --rootdir option"

for isolation in simple nspawn; do
    rootdir=$WORKDIR/$isolation
    runcmd "$MOCKCMD --isolation=$isolation --rootdir=$rootdir --scrub=chroot"
    runcmd "$MOCKCMD --isolation=$isolation --rootdir=$rootdir --scrub=bootstrap"
    runcmd "$MOCKCMD --isolation=$isolation --rootdir=$rootdir --bootstrap-chroot ${TESTDIR}/test-C-1.1-0.src.rpm"
done
