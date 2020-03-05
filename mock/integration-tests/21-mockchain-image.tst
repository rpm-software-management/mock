#!/bin/sh

if test -z "$TESTDIR"; then
    TESTDIR=$(dirname "$(readlink -f "$0")")
fi

. ${TESTDIR}/functions

: "${MOCKCHAIN=mockchain}"
: "${MOCK=mock}"

header "mockchain with --use-bootstap-image"

test "$(rpm -qa podman | wc -l)" -eq 1 || die "podman package needs to be installed"

runcmd "$MOCKCMD --scrub=chroot"
runcmd "$MOCKCMD --scrub=bootstrap"
runcmd "$MOCKCHAIN --use-bootstrap-image ${TESTDIR}/test-C-1.1-0.src.rpm ${TESTDIR}/test-B-1.1-0.src.rpm ${TESTDIR}/test-A-1.1-0.src.rpm"
