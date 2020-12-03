#!/bin/bash

storage=https://raw.githubusercontent.com/rpm-software-management/mock-test-data/main
srpm_version1=$storage/mock-test-bump-version-1-0.src.rpm
srpm_version2=$storage/mock-test-bump-version-2-0.src.rpm

: "${MOCKCMD=mock}"
if test -z "$TESTDIR"; then
    TESTDIR=$(dirname "$(readlink -f "$0")")
fi

. "${TESTDIR}"/functions

header "testing that root-cache gets updated if buildroot is updated"

confdir=$HOME/.config
mkdir -p "$confdir"

local_config=$confdir/mock.cfg

test -f "$local_config" && die "please remove $local_config first"

TMPDIR=$(mktemp -d) || die "can't create temporary directory"
REPODIR=$TMPDIR/local_repo
mkdir "$REPODIR"

createrepo_c "$REPODIR"

cat > "$local_config" <<EOF
config_opts["dnf.conf"] += """
[local_repo]
name=local_repo
baseurl=$REPODIR
gpgcheck=0
skip_if_unavailable=0
"""
EOF

cleanup() {
    rm "$local_config"
    rm -rf "$TMPDIR"
}
trap cleanup EXIT

tarball_stat=
assert_changed_cache()
{
    echo "= Checking if the tarball is updated, expected $1 ="

    new_stat=$(stat "/var/cache/mock/$testConfig/root_cache/cache.tar.gz" | grep -v Access)

    result=yes
    if test "$new_stat" = "$tarball_stat"; then
        result=no
    fi

    test "$result" = "$1" || {
        echo "=== new ==="
        echo "$new_stat"
        echo "=== old ==="
        echo "$tarball_stat"
        echo "==========="
        die "Expected '$1', but result is '$result'"
    }

    tarball_stat=$new_stat
}

# Put the first RPMs into buildroot.
runcmd "$MOCKCMD --rebuild $srpm_version1 --resultdir $REPODIR" \
    || die "mock rebuild 1 failed"
createrepo_c "$REPODIR"
assert_changed_cache yes

runcmd "$MOCKCMD --scrub=chroot --scrub=root-cache" || die "mock scrub short failed"

# Make sure the mock-test-bump-version is installed into minimal chroot
echo "config_opts['chroot_setup_cmd'] += ' mock-test-bump-version'" >> "$local_config"

# Build the updated package and recreate the repository
runcmd "$MOCKCMD --rebuild $srpm_version2 --resultdir $REPODIR" \
    || die "mock rebuild 2 (additional package in buildroot) failed"
createrepo_c "$REPODIR"
assert_changed_cache yes

# Now the package should be auto-updated by mock, and root-cache tarball re-created.
runcmd "$MOCKCMD --rebuild $srpm_version2 --resultdir $REPODIR" \
    || die "mock rebuild 3 (updated package in buildroot) failed"
assert_changed_cache yes

# The updated package is already there, so nothing is upgraded - and also no
# new new tarball crated
rm "$REPODIR/root.log"
runcmd "$MOCKCMD --rebuild $srpm_version2 --resultdir $REPODIR" \
    || die "mock rebuild 4 (updated package already in buildroot) failed"
assert_changed_cache no

runcmd "$MOCKCMD --scrub=all" || die "mock scrub failed"

exit 0
