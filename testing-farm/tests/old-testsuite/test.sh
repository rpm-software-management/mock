#!/bin/sh -eux

cd ../../../mock

# Install the tested RPMs
install-mock-packages-built-by-packit mock-core-configs mock

# Download the tested SRPM
SRPM_DOWNLOAD_DIR=/tmp/mock-test-srpms install-mock-packages-built-by-packit mock

if make check >the-log 2>&1; then
    grep -e FAILED: -e PASSED: the-log
    echo "The 'make check' testsuite passed."
else
    grep -e FAILED: -e PASSED: the-log
    cat the-log
    exit 1
fi
