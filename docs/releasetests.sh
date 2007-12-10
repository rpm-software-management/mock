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

set -e
set -x

DIR=$(cd $(dirname $0); pwd)
TOP_SRCTREE=$DIR/../
cd $TOP_SRCTREE

make distclean ||:
./configure
make distcheck
make srpm
gcc -o docs/daemontest docs/daemontest.c

#
# most tests below will use this mock command line
# 
testConfig=fedora-8-x86_64
uniqueext="$$-$RANDOM"
MOCKCMD="sudo ./py/mock.py --resultdir=$TOP_SRCTREE/mock-unit-test --uniqueext=$uniqueext -r $testConfig $MOCK_EXTRA_ARGS"
CHROOT=/var/lib/mock/${testConfig}-$uniqueext/root

# clear out any old test results
sudo rm -rf $TOP_SRCTREE/mock-unit-test

# clear out root cache so we get at least run without root cache present
sudo rm -rf /var/lib/mock/cache/${testConfig}/root_cache

#
# pre-populate yum cache for the rest of the commands below
#
time $MOCKCMD --init
time $MOCKCMD --installdeps mock-*.src.rpm
if [ ! -e $CHROOT/usr/include/python* ]; then
    echo "installdeps test FAILED. could not find /usr/include/python*"
    exit 1
fi

#
# Test offline build
#
time $MOCKCMD --offline --rebuild mock-*.src.rpm
if [ ! -e mock-unit-test/mock-*.x86_64.rpm ]; then
    echo "rebuild test FAILED. could not find mock-unit-test/mock-*.x86_64.rpm"
    exit 1
fi

#
# Test orphanskill feature (std)
#
if pgrep daemontest; then
    echo "Exiting because there is already a daemontest running."
    exit 1
fi
time $MOCKCMD --offline --init
cp docs/daemontest $CHROOT/tmp
time $MOCKCMD --offline --chroot -- /tmp/daemontest
if pgrep daemontest; then
    echo "Daemontest FAILED. found a daemontest process running after exit." 
    exit 1
fi

#
# Test orphanskill feature (explicit)
#
time $MOCKCMD --offline --init
cp docs/daemontest $CHROOT/tmp
echo -e "#!/bin/sh\n/tmp/daemontest\nsleep 60\n" >> $CHROOT/tmp/try
# the following should launch about three processes in the chroot: bash, sleep, daemontest
$MOCKCMD --offline --chroot -- bash /tmp/try &
mockpid=$!
sleep 1
# now we 'prematurely' kill mock. This should leave the three orphans above
sudo kill -9 $mockpid
if ! pgrep daemontest; then
    echo "Daemontest failed. daemontest should be running now but is not."
    exit 1
fi
$MOCKCMD --offline --orphanskill 
if pgrep daemontest; then
    echo "Daemontest FAILED. found a daemontest process running after exit." 
    exit 1
fi


#
# test init/clean
#
time $MOCKCMD --offline --clean
if [ -e $CHROOT ]; then
    echo "clean test FAILED. still found $CHROOT dir."
    exit 1
fi

time $MOCKCMD --offline --init
time $MOCKCMD --offline --install ccache
if [ ! -e $CHROOT/usr/bin/ccache ]; then
    echo "init/clean test FAILED. ccache not found."
    exit 1
fi

#
# test old-style cmdline options
#
time $MOCKCMD --offline clean
time $MOCKCMD --offline init
time $MOCKCMD --offline install ccache
if [ ! -e $CHROOT/usr/bin/ccache ]; then
    echo "init/clean test FAILED. ccache not found."
    exit 1
fi

#
# Test build all configs we ship.
#
for i in $(ls etc/mock | grep .cfg | grep -v default | grep -v ppc); do
    time sudo ./py/mock.py --resultdir=$TOP_SRCTREE/mock-unit-test --uniqueext=$uniqueext rebuild mock-*.src.rpm  -r $(basename $i .cfg) $MOCK_EXTRA_ARGS
done


