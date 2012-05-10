#!/bin/sh

source ${TESTDIR}/functions

#
# Test that chroot with more than one arg is not getting passed through a shell
#
header "Test that chroot with more than one arg is not getting passed through a shell"
runcmd "$MOCKCMD --offline --chroot touch '/tmp/{quux,wibble}'"
if [ ! -f $CHROOT/tmp/\{quux,wibble\} ] || [ -f $CHROOT/tmp/quux ] || [ -f $CHROOT/tmp/wibble ]; then
    echo "'mock --chroot' with more than one argument is being passed to os.system()"
    exit 1
fi

