#!/bin/sh
set -e
mkdir -p build 2>&1
aclocal
libtoolize -c --force --automake
automake --force --foreign --add-missing -c
autoconf --force
