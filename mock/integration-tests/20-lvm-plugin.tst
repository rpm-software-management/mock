#!/bin/bash


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

cat > "$local_config" <<EOF
config_opts['plugin_conf']['root_cache_enable'] = False
config_opts['plugin_conf']['lvm_root_enable'] = True
config_opts['plugin_conf']['lvm_root_opts'] = {
    'volume_group': 'mock',
    'size': '4G',
    'pool_name': 'pool',
    'umount_root': False
}
EOF

cleanup() {
    rm "$local_config"
    rm -rf "$TMPDIR"
}
trap cleanup EXIT

runcmd "$MOCKCMD --rebuild ${TESTDIR}/test-C-1.1-0.src.rpm --resultdir $TMPDIR" \
    || die "mock rebuild failed"

runcmd "$MOCKCMD --shell '/bin/true'" || die "mock shell failed"

mkdir $TMPDIR/repodir || die "can't create repodir inside tmpdir"
curl https://kojipkgs.fedoraproject.org//packages/python-copr-common/0.6/1.fc32/noarch/python3-copr-common-0.6-1.fc32.noarch.rpm \
    --output $TMPDIR/repodir/python3-copr-common-0.6-1.fc32.noarch.rpm || die "failed to download old rpm package"

runcmd "createrepo_c $TMPDIR/repodir" || die "failed to run createrepo"

cat >> "$local_config" <<EOF
config_opts['root'] = 'testrepo'
config_opts['chroot_setup_cmd'] = 'install python3-copr-common'

config_opts['yum.conf'] += """

[testrepo]
name=testrepo
baseurl=file://$TMPDIR/repodir
"""
EOF

runcmd "$MOCKCMD --rebuild ${TESTDIR}/test-C-1.1-0.src.rpm --resultdir $TMPDIR" \
    | grep "created updated snapshot" || die "creating updated snapshot failed"

runcmd "$MOCKCMD --scrub=all" || die "mock scrub failed"

# repeated run should succeed as well, rhbz#1805179
runcmd "$MOCKCMD --scrub=all" || die "mock scrub failed"

exit 0
