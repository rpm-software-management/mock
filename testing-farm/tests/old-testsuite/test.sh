#!/bin/bash -eux

# The Mock's test-suite is designed for the mockbuild users.  Copy files to a
# separate directory where the 'mockbuild' user has a full access.
workdir=$(mktemp -d --suffix=-mock-old-tests)
rsync -ra ../../../ "$workdir"
chown -R mockbuild:mockbuild "$workdir"

# TODO: Mock should work with 'rw-------' files too.
# https://github.com/rpm-software-management/mock/issues/1300
chmod a+r "$workdir/mock/integration-tests"/test-*

# Install the tested RPMs
install-mock-packages-built-by-packit mock-core-configs mock

# Download the tested SRPM
SRPM_DOWNLOAD_DIR=/tmp/mock-test-srpms install-mock-packages-built-by-packit mock

cd "$workdir/mock"

# We want to provide rather short live logs ASAP, hence that grep.  Full logs
# are provided later no matter the exit status.
exit_status=0
sudo -E -u mockbuild make check |& tee the-log | grep -e FAILED: -e PASSED: || {
    exit_status=$?
}
cat the-log
exit $exit_status
