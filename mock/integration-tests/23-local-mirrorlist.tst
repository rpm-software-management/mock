#!/bin/sh

if test -z "$TESTDIR"; then
    TESTDIR=$(dirname "$(readlink -f "$0")")
fi

. "${TESTDIR}/functions"
set -e

: "${MOCKCMD=mock}"

header "mock and local mirrorlist with expanded variables"

TMPDIR=$(mktemp -d)
cleanup() { rm -rf "$TMPDIR"; }
trap cleanup EXIT

mirrorlist=$TMPDIR/x86_64/mirrorlist
config=$TMPDIR/rawhide.cfg

mkdir "$(dirname "$mirrorlist")"
cat > "$mirrorlist" <<EOF
https://raw.githubusercontent.com/rpm-software-management/mock-test-data/main/repo/
EOF

# "local" mirror list pointing to external repository hosted on GitHub.
cat > "$config" <<EOF
include("fedora-rawhide-x86_64.cfg")
config_opts["root"] = "test-local-mirrorlist"
config_opts["dnf.conf"] +=  """
[always_available]
name=Always Available
mirrorlist=$TMPDIR/\$basearch/mirrorlist
gpgcheck=0
"""
EOF

for isolation in simple nspawn; do
    for bootstrap in bootstrap-chroot no-bootstrap-chroot; do
        mock="$MOCKCMD --isolation=$isolation  --$bootstrap -r $config"
        $mock --install always-installable
        $mock --scrub=chroot
        $mock --scrub=bootstrap
    done
done
