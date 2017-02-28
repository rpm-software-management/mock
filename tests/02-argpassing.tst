#!/bin/sh

. ${TESTDIR}/functions

#
# Test that chroot with one arg is getting passed though a shell (via os.system())
#
header "testing that args are passed correctly to a shell"
runcmd "$MOCKCMD --offline --disable-plugin=tmpfs --chroot 'touch /var/tmp/{foo,bar,baz}'"
if [ ! -f $CHROOT/var/tmp/foo ] || [ ! -f $CHROOT/var/tmp/bar ] || [ ! -f $CHROOT/var/tmp/baz ]; then
    echo "'mock --chroot' with one argument is not being passed to os.system()"
    exit 1
fi

