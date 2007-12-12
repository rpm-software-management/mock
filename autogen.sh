#!/bin/sh

# run this script to create all the autotools fluff

set -e
mkdir -p build 2>&1
aclocal
automake --force --foreign --add-missing -c
autoconf --force
