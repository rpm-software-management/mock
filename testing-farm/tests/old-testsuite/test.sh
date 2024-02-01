#!/bin/bash -eux

# Copy files so the 'mockbuild' user has the full access
workdir=$(mktemp -d --suffix=-mock-old-tests)
rsync -rav ../../../ "$workdir"
chown -Rv mockbuild:mockbuild "$workdir"

# TODO: Mock should work with 'rw-------' files too.
# https://github.com/rpm-software-management/mock/issues/1300
chmod a+r "$workdir/mock/integration-tests"/test-*

# Install the tested RPMs
install-mock-packages-built-by-packit mock-core-configs mock

# Download the tested SRPM
SRPM_DOWNLOAD_DIR=/tmp/mock-test-srpms install-mock-packages-built-by-packit mock

# Testsuite is prepared for the mockbuild user

cd "$workdir/mock"
if (sudo -E -u mockbuild make check > >(tee the-log | grep -e FAILED: -e PASSED:) 2>&1) >&2; then
    echo "The 'make check' testsuite passed."
else
    cat the-log
    exit 1
fi
