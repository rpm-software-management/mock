#!/bin/sh

. ${TESTDIR}/functions

# Test that we use nspawn by default

header "Test nspawn default"
output=$($MOCKCMD --shell 'echo $PPID')

case $output in
    1) ;;
    *) die "Looks like systemd-nspawn isn't used, unexpected output '$output'" ;;
esac
