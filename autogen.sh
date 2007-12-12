#!/bin/sh
set -e
mkdir -p build 2>&1
automake --force --foreign --add-missing -c
autoconf --force
