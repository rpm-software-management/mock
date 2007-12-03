#!/bin/sh
# vim:tw=0:ts=4:sw=4

# this is a test script to run everything through its paces before you do a
# release. The basic idea is:

# 1) make distcheck to ensure that all autoconf stuff is setup properly
# 2) rebuild mock srpm using this version of mock under all distributed configs

# This test will only run on a machine with full access to internet.
# might work with http_proxy= env var, but I havent tested that.

set -e
set -x

DIR=$(cd $(dirname $0); pwd)
TOP_SRCTREE=$DIR/../
cd $TOP_SRCTREE

make distclean ||:
./configure
make distcheck
make srpm
make src/daemontest

#
# most tests below will use this mock command line
# 
testConfig=fedora-8-x86_64
MOCKCMD="sudo ./py/mock.py --resultdir=$TOP_SRCTREE/mock-unit-test --uniqueext=unittest -r $testConfig"
CHROOT=/var/lib/mock/${testConfig}-unittest/root

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
# Test orphanskill feature
#
if pgrep daemontest; then
    echo "Exiting because there is already a daemontest running."
    exit 1
fi
time $MOCKCMD --offline --init
cp src/daemontest $CHROOT/tmp
time $MOCKCMD --offline --chroot -- /tmp/daemontest
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
sudo rm -rf $TOP_SRCTREE/mock-unit-test
for i in $(ls etc/mock | grep .cfg | grep -v default | grep -v ppc); do
    time sudo ./py/mock.py --resultdir=$TOP_SRCTREE/mock-unit-test --uniqueext=unittest rebuild mock-*.src.rpm  -r $(basename $i .cfg)
done


