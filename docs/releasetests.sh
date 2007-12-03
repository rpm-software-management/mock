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
MOCKCMD="time sudo ./py/mock.py --resultdir=$TOP_SRCTREE/mock-unit-test --uniqueext=unittest -r $testConfig"
CHROOT=/var/lib/mock/$testConfig/root

#
# pre-populate yum cache for the rest of the commands below
#
$MOCKCMD --init
$MOCKCMD --installdeps mock-*.src.rpm

#
# Test offline build
#
$MOCKCMD --offline --rebuild mock-*.src.rpm

#
# Test orphanskill feature
#
(pgrep daemontest && echo "Exiting because there is already a daemontest running." && exit 1) || :
$MOCKCMD --offline --init
cp src/daemontest $CHROOT/tmp
$MOCKCMD --offline --chroot -- /tmp/daemontest
(pgrep daemontest && echo "Daemontest FAILED. found a daemontest process running after exit." && exit 1) || :

#
# test init/clean
#
$MOCKCMD --offline --clean
$MOCKCMD --offline --init
$MOCKCMD --offline --install ccache
[ -e $CHROOT/usr/bin/ccache ] || (echo "init/clean test FAILED. ccache not found." && exit 1)

#
# test old-style cmdline options
#
$MOCKCMD --offline clean
$MOCKCMD --offline init
$MOCKCMD --offline install ccache
[ -e $CHROOT/usr/bin/ccache ] || (echo "init/clean test FAILED. ccache not found." && exit 1)

#
# Test build all configs we ship.
#
sudo rm -rf $TOP_SRCTREE/mock-unit-test
for i in $(ls etc/mock | grep .cfg | grep -v default | grep -v ppc); do
    time sudo ./py/mock.py --resultdir=$TOP_SRCTREE/mock-unit-test --uniqueext=unittest rebuild mock-*.src.rpm  -r $(basename $i .cfg)
done


