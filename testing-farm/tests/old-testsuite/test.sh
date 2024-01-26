#!/bin/sh -eux

cd ../../../mock
install-mock-packages-built-by-packit mock-core-configs mock

if make check 2>&1 | tee the-log | grep FAILED: -e PASSED:; then
    true
else
    cat the-log
fi
