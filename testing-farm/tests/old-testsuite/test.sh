#!/bin/sh -eux

cd ../../../mock

env

install-mock-packages-built-by-packit mock-core-configs mock

if make check 2>&1 | tee the-log | grep -e FAILED: -e PASSED:; then
    true
else
    cat the-log
fi
