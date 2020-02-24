#!/bin/sh

. ${TESTDIR}/functions

#
# Test that chroot with more than one arg is not getting passed through a shell
#
header "Test that chroot with more than one arg is not getting passed through a shell"
runcmd "$MOCKCMD --offline --disable-plugin=tmpfs --chroot touch '/var/tmp/{quux,wibble}'"
if [ ! -f $CHROOT/var/tmp/\{quux,wibble\} ] || [ -f $CHROOT/var/tmp/quux ] || [ -f $CHROOT/var/tmp/wibble ]; then
    echo "'mock --chroot' with more than one argument is being passed to os.system()"
    exit 1
fi

