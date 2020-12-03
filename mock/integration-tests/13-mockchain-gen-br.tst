#!/bin/sh

if test -z "$TESTDIR"; then
    TESTDIR=$(dirname "$(readlink -f "$0")")
fi

. ${TESTDIR}/functions

: "${MOCKCHAIN=mockchain}"

header "online mockchain, tmpfs.keep_mounted=True, nosync and one package having generated BuildRequires"

test "$(rpm -qa nosync | wc -l)" -eq 2 || die "nosync.x86_64 and nosync.i686 needs to be installed"

confdir=$HOME/.config
mkdir -p "$confdir"
local_config=$confdir/mock.cfg

# cleanup potentially mounted stuff we'll overmount by tmpfs
runcmd "$MOCKCHAIN --scrub=all"

test -f "$local_config" && die "please remove $local_config first"

cat > "$local_config" <<EOF
config_opts['plugin_conf']['tmpfs_enable'] = True
config_opts['plugin_conf']['tmpfs_opts']['keep_mounted'] = True
config_opts['nosync'] = True
EOF
cleanup() {
    rm "$local_config"
}
trap cleanup EXIT

packages="
    https://github.com/rpm-software-management/mock-test-data/raw/main/python-copr-999-1.src.rpm
    https://github.com/rpm-software-management/mock-test-data/raw/main/dep-on-python-copr-999-1-0.src.rpm
"

eval 'set -- $packages'
runcmd "$MOCKCHAIN $*" || die "mockchain build failed"

# cleanup the tmpfs stuff before we de-configure tmpfs
runcmd "$MOCKCHAIN --scrub=all" || die "scrub failed"
