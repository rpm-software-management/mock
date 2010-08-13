#!/bin/sh
# vim:tw=0:ts=4:sw=4

# this is a test script to run everything through its paces before you do a
# release. The basic idea is:

# 1) make distcheck to ensure that all autoconf stuff is setup properly
# 2) run some basic tests to test different mock options.
# 3) rebuild mock srpm using this version of mock under all distributed configs

# This test will only run on a machine with full access to internet.
# might work with http_proxy= env var, but I havent tested that.
# 
# This test script expects to be run on an x86_64 machine. It will *not* run
# properly on an i386 machine.
#

CURDIR=$(pwd)

source ${CURDIR}/tests/functions

MOCKSRPM=${CURDIR}/mock-*.src.rpm
DIR=$(cd $(dirname $0); pwd)
TOP_SRCTREE=$DIR/../
cd $TOP_SRCTREE

#
# most tests below will use this mock command line
# 
testConfig=fedora-13-x86_64
uniqueext="$$-$RANDOM"
outdir=${CURDIR}/mock-unit-test
MOCKCMD="sudo ./py/mock.py --resultdir=$outdir --uniqueext=$uniqueext -r $testConfig $MOCK_EXTRA_ARGS"
CHROOT=/var/lib/mock/${testConfig}-$uniqueext/root

trap '$MOCKCMD --clean; exit 1' INT HUP QUIT EXIT TERM

export CURDIR MOCKSRPM DIR TOP_SRCTREE testConfig uniqueext outdir MOCKCMD CHROOT

# clear out root cache so we get at least run without root cache present
#sudo rm -rf /var/lib/mock/cache/${testConfig}/root_cache

#
# pre-populate yum cache for the rest of the commands below
#
header "pre-populating the cache"
runcmd "$MOCKCMD --init"
runcmd "$MOCKCMD --installdeps $MOCKSRPM"
if [ ! -e $CHROOT/usr/include/python* ]; then
    echo "installdeps test FAILED. could not find /usr/include/python*"
    exit 1
fi

fails=0

#
# run regression tests
#
for i in ${CURDIR}/tests/*.tst; do
    sh $i
    if [ $? != 0 ]; then
	fails=$(($fails + 1))
	echo "**************** $i failed"
    fi
done

msg=$(printf "%d regression failures\n" $fails)
header "$msg"

#
# clean up
#
header "clean up from first round of tests"
runcmd "$MOCKCMD --offline --clean"

#
# Test build all configs we ship.
#
for i in $(ls etc/mock | grep .cfg | grep -v default | egrep -v 'ppc|s390|sparc'); do
    MOCKCMD="sudo ./py/mock.py --resultdir=$outdir --uniqueext=$uniqueext -r $(basename $i .cfg) $MOCK_EXTRA_ARGS"
    if [ "${i#epel-4-x86_64.cfg}" != "" ]; then
	header "testing config $(basename $i .cfg) with tmpfs plugin"
	runcmd "$MOCKCMD --enable-plugin=tmpfs --rebuild $MOCKSRPM "
	if [ $? != 0 ]; then 
	    echo "FAILED!"
	    fails=$(($fails+1))
	fi
    fi
    header "testing config $(basename $i .cfg) *without* tmpfs plugin"
    runcmd "$MOCKCMD                       --rebuild $MOCKSRPM"
    if [ $? != 0 ]; then 
	echo "FAILED!"
	fails=$(($fails+1))
    fi
done

msg=$(printf "%d total failures\n" $fails)
header "$msg"
exit $fails
