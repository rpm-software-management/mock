#!/bin/sh -eux

cd ../../../mock
install-mock-packages-built-by-packit mock-core-configs mock
make check 2>&1 | tee the-log | grep -e ^PASS -e ^FAIL -e ^ERROR
