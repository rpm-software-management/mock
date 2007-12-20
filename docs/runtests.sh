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

CURDIR=$(pwd)
MOCKSRPM=${CURDIR}/mock-*.src.rpm
DIR=$(cd $(dirname $0); pwd)
TOP_SRCTREE=$DIR/../
cd $TOP_SRCTREE

#
# most tests below will use this mock command line
# 
testConfig=fedora-8-x86_64
uniqueext="$$-$RANDOM"
outdir=${CURDIR}/mock-unit-test
MOCKCMD="sudo ./py/mock.py --resultdir=$outdir --uniqueext=$uniqueext -r $testConfig $MOCK_EXTRA_ARGS"
CHROOT=/var/lib/mock/${testConfig}-$uniqueext/root

trap '$MOCKCMD --clean' INT HUP QUIT EXIT TERM

# clear out root cache so we get at least run without root cache present
#sudo rm -rf /var/lib/mock/cache/${testConfig}/root_cache

#
# pre-populate yum cache for the rest of the commands below
#
time $MOCKCMD --init
time $MOCKCMD --installdeps $MOCKSRPM
if [ ! -e $CHROOT/usr/include/python* ]; then
    echo "installdeps test FAILED. could not find /usr/include/python*"
    exit 1
fi

#
# Test that chroot return code is properly passed up
#
set +e
time $MOCKCMD --offline --chroot -- bash -c "exit 5"
if [ $? -ne 5 ]; then
    echo "'mock --chroot' return code not properly passed back."
    exit 1
fi
set -e

#
# test mock shell (interactive) and return code passing
#
set +e
echo exit 5 | time $MOCKCMD --offline --shell
if [ $? -ne 5 ]; then
    echo "'mock --chroot' return code not properly passed back."
    exit 1
fi
set -e

#
# Test that chroot with one arg is getting passed though a shell (via os.system())
#
time $MOCKCMD --offline --chroot 'touch /tmp/{foo,bar,baz}'
if [ ! -f $CHROOT/tmp/foo ] || [ ! -f $CHROOT/tmp/bar ] || [ ! -f $CHROOT/tmp/baz ]; then
    echo "'mock --chroot' with one argument is not being passed to os.system()"
    exit 1
fi

#
# Test that chroot with more than one arg is not getting passed through a shell
#
time $MOCKCMD --offline --chroot touch '/tmp/{quux,wibble}'
if [ ! -f $CHROOT/tmp/\{quux,wibble\} ] || [ -f $CHROOT/tmp/quux ] || [ -f $CHROOT/tmp/wibble ]; then
    echo "'mock --chroot' with more than one argument is being passed to os.system()"
    exit 1
fi

#
# Test offline build as well as tmpfs
#
time $MOCKCMD --offline --enable-plugin=tmpfs --rebuild $MOCKSRPM
if [ ! -e $outdir/mock-*.noarch.rpm ]; then
    echo "rebuild test FAILED. could not find $outdir/mock-*.noarch.rpm"
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
time $MOCKCMD --offline --copyin docs/daemontest.c /tmp
time $MOCKCMD --offline --chroot -- gcc -Wall -o /tmp/daemontest /tmp/daemontest.c
time $MOCKCMD --offline --chroot -- /tmp/daemontest
if pgrep daemontest; then
    echo "Daemontest FAILED. found a daemontest process running after exit." 
    exit 1
fi

#
# Test orphanskill feature (explicit)
#
time $MOCKCMD --offline --init
time $MOCKCMD --offline --copyin docs/daemontest.c /tmp
time $MOCKCMD --offline --chroot -- gcc -Wall -o /tmp/daemontest /tmp/daemontest.c
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
# clean up from first round of tests
#
time $MOCKCMD --offline --clean

#
# Test build all configs we ship.
#
for i in $(ls etc/mock | grep .cfg | grep -v default | grep -v ppc); do
    MOCKCMD="sudo ./py/mock.py --resultdir=$outdir --uniqueext=$uniqueext -r $(basename $i .cfg) $MOCK_EXTRA_ARGS"
    # test tmpfs and normal
    time $MOCKCMD --enable-plugin=tmpfs --rebuild $MOCKSRPM 
    time $MOCKCMD                       --rebuild $MOCKSRPM 
done


