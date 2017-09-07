#!/bin/sh

. ${TESTDIR}/functions

#
# Test offline build as well as tmpfs
#
header "Test offline build as well as tmpfs"
runcmd "$MOCKCMD --offline --enable-plugin=tmpfs --rebuild $MOCKSRPM"
if [ ! -e $outdir/mock-*.noarch.rpm ]; then
    echo "rebuild test FAILED. could not find $outdir/mock-*.noarch.rpm"
    exit 1
fi

