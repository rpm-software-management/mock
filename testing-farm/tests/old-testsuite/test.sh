#!/bin/sh -eux

cd ../../../mock

install-mock-packages-built-by-packit mock-core-configs mock

if make check >the-log 2>&1; then
    echo "The 'make check' testsuite passed."
else
    grep -e FAILED: -e PASSED: the-log
fi
