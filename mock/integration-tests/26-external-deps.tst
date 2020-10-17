#!/bin/sh

. ${TESTDIR}/functions

#
# Test offline build as well as tmpfs
#
header "Test external deps"
runcmd "$MOCKCMD --offline --config-opts=external_buildrequires=True test-F-0-1.fc33.src.rpm"
if [ ! -e $outdir/mock-*.noarch.rpm ]; then
    echo "rebuild test FAILED. could not find $outdir/mock-*.noarch.rpm"
    exit 1
fi

