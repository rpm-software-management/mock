#!/bin/sh
# vim:tw=0:ts=4:sw=4

# this is a test script to run everything through its paces before you do a
# release. The basic idea is:

# 1) make distcheck to ensure that all autoconf stuff is setup properly
# 2) build and install mock rpm.
# 3) then use that version of mock to recompile the mock srpm for all supported distros.

# This test will only run on a machine with full access to internet.
# might work with http_proxy= env var, but I havent tested that.

set -e
set -x

DIR=$(cd $(dirname $0); pwd)
TOP_SRCTREE=$DIR/../
cd $TOP_SRCTREE

[ ! -e Makefile ] || make distclean

./configure
make distcheck
make rpm

sudo rpm -e mock
sudo rpm -Uvh --replacepkgs $(ls mock*.rpm | grep -v src.rpm | grep -v debuginfo)

for i in $(ls $DIR/../etc/*cfg | grep -v default); do
    mock --resultdir=$TOP_SRCTREE/mock-unit-test --uniqueext=unittest rebuild mock-0.8.0-1.fc7.src.rpm  -r fedora-4-i386-epel
done

