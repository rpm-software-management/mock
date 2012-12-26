#!/bin/sh

. ${TESTDIR}/functions

#
# Test that chroot with one arg is getting passed though a shell (via os.system())
#
header "testing that args are passed correctly to a shell"
runcmd "$MOCKCMD --offline --chroot 'touch /tmp/{foo,bar,baz}'"
if [ ! -f $CHROOT/tmp/foo ] || [ ! -f $CHROOT/tmp/bar ] || [ ! -f $CHROOT/tmp/baz ]; then
    echo "'mock --chroot' with one argument is not being passed to os.system()"
    exit 1
fi

