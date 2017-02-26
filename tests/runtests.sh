#!/bin/sh
# vim:tw=0:ts=4:sw=4

# this is a test script to run everything through its paces before you do a
# release. The basic idea is:

# 1) make distcheck to ensure that all autoconf stuff is setup properly
# 2) run some basic tests to test different mock options.
# 3) rebuild mock srpm using this version of mock under all distributed configs

# This test will only run on a machine with full access to internet.
# might work with http_proxy= env var, but I havent tested that.
#
# This test script expects to be run on an x86_64 machine. It will *not* run
# properly on an i386 machine.
#

#VERBOSE=
VERBOSE=--verbose
export VERBOSE

d=$(cd $(dirname $0); pwd)
. $d/testenvironment
. ${TESTDIR}/functions

trap '$MOCKCMD --clean; exit 1' INT HUP QUIT TERM

# clear out root cache so we get at least run without root cache present
#sudo rm -rf /var/lib/mock/cache/${testConfig}/root_cache

#
# pre-populate yum cache for the rest of the commands below
#

if [ -e /usr/bin/dnf ]; then
    header "pre-populating the cache (DNF)"
    runcmd "$MOCKCMD --init --dnf"
    header "clean up"
    runcmd "$MOCKCMD --offline --clean"
else
    header "pre-populating the cache (YUM)"
    runcmd "$MOCKCMD --init"
fi
header "installing dependencies for $MOCKSRPM"
runcmd "$MOCKCMD --disable-plugin=tmpfs --installdeps $MOCKSRPM"
if [ ! -e $CHROOT/usr/include/python* ]; then
echo "installdeps test FAILED. could not find /usr/include/python*"
exit 1
fi

header "running regression tests"
sh ${TESTDIR}/runregressions.sh
fails=$?

msg=$(printf "%s regression failures\n" $fails)
header "$msg"

#
# clean up
#
header "clean up from first round of tests"
runcmd "$MOCKCMD --offline --clean"

header "running configuration tests"
sh ${TESTDIR}/runconfigs.sh
cfgfails=$?

msg=$(printf "%d total failures\n" $(($fails+$cfgfails)))
header "$msg"
exit $fails
