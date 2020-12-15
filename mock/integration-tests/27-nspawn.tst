#!/bin/sh

. ${TESTDIR}/functions

# Test that we use nspawn by default

header "Test nspawn default"
test $($MOCKCMD --shell 'echo $PPID') -eq 1 || die "Looks like nspanw isn't used"
