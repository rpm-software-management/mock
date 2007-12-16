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
./autogen.sh
./configure
make distcheck
make srpm
make check
