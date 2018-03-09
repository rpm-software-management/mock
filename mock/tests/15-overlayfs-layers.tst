#!/bin/sh
# This file is simple shell wrapper for overlayfs_layers_test.py test.
# For more details about test itself look into test's file.

set -e

onExit() {
    if [ -n "${tmpDir}" ] ; then
        rm -rf "${tmpDir}"
    fi
}

if [ -z "${TESTDIR:-}" ] ; then
    TESTDIR="$( cd "$( dirname "$0" )" && pwd )"
fi

. ${TESTDIR}/functions

header "Overlayfs layers test"

pluginsDir="$( dirname "${TESTDIR}" )/py/mockbuild/plugins"
overlayfsPluginFile="${pluginsDir}/overlayfs.py"
testFileName="overlayfs_layers_test.py"

tmpDir="$( mktemp -d )"
trap onExit EXIT

# move python files and execute everything in tmpDir, so test finds overlayfs
# module and also .pyc file(s) are then generated there
cp "${overlayfsPluginFile}" "${tmpDir}"
cp "${TESTDIR}/${testFileName}" "${tmpDir}"
cd "${tmpDir}"
runcmd "python ${testFileName}"
