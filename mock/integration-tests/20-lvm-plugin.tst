#!/bin/bash

storage=https://raw.githubusercontent.com/rpm-software-management/mock-test-data/main
srpm_version1=$storage/mock-test-bump-version-1-0.src.rpm
srpm_version2=$storage/mock-test-bump-version-2-0.src.rpm

: "${MOCKCMD=mock}"
if test -z "$TESTDIR"; then
    TESTDIR=$(dirname "$(readlink -f "$0")")
fi

. ${TESTDIR}/functions

header "testing that lvm plugin works"

confdir=$HOME/.config
mkdir -p "$confdir"

test -f "/test-lvm-disk" || die "Please run prepare-lvm.sh first"

local_config=$confdir/mock.cfg

test -f "$local_config" && die "please remove $local_config first"

TMPDIR=$(mktemp -d) || die "can't create temporary directory"
REPODIR=$TMPDIR/local_repo
mkdir "$REPODIR"

createrepo_c "$REPODIR"

cat > "$local_config" <<EOF
config_opts['plugin_conf']['root_cache_enable'] = False
config_opts['plugin_conf']['lvm_root_enable'] = True
config_opts['plugin_conf']['lvm_root_opts'] = {
    'volume_group': 'mock',
    'size': '4G',
    'pool_name': 'pool',
    'umount_root': False
}

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

additional_snapshots_assert()
{
    echo "= Checking number of snapshots ="
    count=$(grep -c "created updated snapshot postinit_updated" "$REPODIR"/root.log)
    test "$count" = "$1" || die "Expected snapshot updates $1, done $count"
}

# Put the first RPMs into buildroot.
runcmd "$MOCKCMD --rebuild $srpm_version1 --resultdir $REPODIR" \
    || die "mock rebuild 1 failed"
createrepo_c "$REPODIR"

runcmd "$MOCKCMD --scrub=chroot --scrub=lvm" || die "mock scrub short failed"

# Make sure the mock-test-bump-version is installed into minimal chroot
echo "config_opts['chroot_setup_cmd'] += ' mock-test-bump-version'" >> "$local_config"

# Build the updated package and recreate the repository
runcmd "$MOCKCMD --rebuild $srpm_version2 --resultdir $REPODIR" \
    || die "mock rebuild 2 (additional package in buildroot) failed"
createrepo_c "$REPODIR"
additional_snapshots_assert 0

# Now the package should be auto-updated by mock, and LVM snapshot re-created.
runcmd "$MOCKCMD --rebuild $srpm_version2 --resultdir $REPODIR" \
    || die "mock rebuild 3 (updated package in buildroot) failed"
additional_snapshots_assert 1

# The updated package is already there, so nothing is upgraded - and also no
# new LVM snapshot should be created
rm "$REPODIR/root.log"
runcmd "$MOCKCMD --rebuild $srpm_version2 --resultdir $REPODIR" \
    || die "mock rebuild 4 (updated package already in buildroot) failed"
additional_snapshots_assert 0

runcmd "$MOCKCMD --shell '/bin/true'" || die "mock shell failed"

runcmd "$MOCKCMD --scrub=all" || die "mock scrub failed"

# repeated run should succeed as well, rhbz#1805179
runcmd "$MOCKCMD --scrub=all" || die "mock scrub failed"

exit 0
