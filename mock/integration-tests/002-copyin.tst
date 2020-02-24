#!/bin/sh

. ${TESTDIR}/functions

#
# Test --copyin
#

header "testing --copyin option"
runcmd "$MOCKCMD --offline --copyin DOESNOTEXIST /"
res=$?
if [ $res -ne 50 ]; then
    echo "'mock --chroot' return code not properly passed back: $res"
    exit 1
fi

runcmd "$MOCKCMD --offline --copyin ${TESTDIR}/test-B-1.1-0.src.rpm ${TESTDIR}/test-C-1.1-0.src.rpm /etc/fstab"
res=$?
if [ $res -ne 50 ]; then
    echo "'mock --chroot' return code not properly passed back: $res"
    exit 1
fi


runcmd "$MOCKCMD --offline --disable-plugin=tmpfs --copyin ${TESTDIR}/test-C-1.1-0.src.rpm /"
res=$?
if [ $res -ne 0 ]; then
   echo "mock returned fail when should have succeeded!"
   exit 1
fi
if [ ! -e $CHROOT/test-C-1.1-0.src.rpm ]; then
    echo "--copyin FAILED. File $CHROOT/test-C-1.1-0.src.rpm not found."
    exit 1
fi

runcmd "$MOCKCMD --offline --disable-plugin=tmpfs --copyin ${TESTDIR}/test-B-1.1-0.src.rpm /test-B-1.1-0.src.rpm"
res=$?
if [ $res -ne 0 ]; then
   echo "mock returned fail when should have succeeded!"
   exit 1
fi
if [ ! -e $CHROOT/test-B-1.1-0.src.rpm ]; then
    echo "--copyin FAILED. File $CHROOT/test-B-1.1-0.src.rpm not found."
    exit 1
fi

TMPDIR=$(mktemp -d)
echo foo > ${TMPDIR}/bar
runcmd "$MOCKCMD --offline --disable-plugin=tmpfs --copyin ${TMPDIR} /foobar"
res=$?
if [ $res -ne 0 ]; then
   echo "mock returned fail when should have succeeded!"
   exit 1
fi
if ! sudo ls -l $CHROOT/foobar/bar; then
    echo "--copyin FAILED. File $CHROOT/foobar/bar not found."
    exit 1
fi

mkdir -p ${TMPDIR}/TMPDIR
echo foo > ${TMPDIR}/TMPDIR/bar
runcmd "$MOCKCMD --offline --disable-plugin=tmpfs --copyin ${TMPDIR}/TMPDIR /"
res=$?
if [ $res -ne 0 ]; then
   echo "mock returned fail when should have succeeded!"
   exit 1
fi
if ! sudo ls -l $CHROOT/TMPDIR/bar; then
    echo "--copyin FAILED. File $CHROOT/TMPDIR/bar not found."
    exit 1
fi


