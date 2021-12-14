#!/bin/bash


: "${MOCKCMD=mock}"
if test -z "$TESTDIR"; then
    TESTDIR=$(dirname "$(readlink -f "$0")")
fi

. ${TESTDIR}/functions

header "testing that sign plugin works"

confdir=$HOME/.config
mkdir -p "$confdir"

case $(rpm --eval "%__gpg") in
    *gpg-mock) ;;
    *) die "this system is not prepared (run setup-box from remote location)" ;;
esac


local_config=$confdir/mock.cfg

test -f "$local_config" && die "please remove $local_config first"

TMPDIR=$(mktemp -d) || die "can't create temporary directory"

cat > "$local_config" <<EOF
config_opts['plugin_conf']['sign_enable'] = True
config_opts['plugin_conf']['sign_opts'] = {}
config_opts['plugin_conf']['sign_opts']['cmd'] = 'rpmsign'
# For the future: Even if change the default, please keep this line
# so we check compatibility.
config_opts['plugin_conf']['sign_opts']['opts'] = '--addsign %(rpms)s'
EOF
cleanup() {
    rm "$local_config"
    rm -rf "$TMPDIR"
}
trap cleanup EXIT

runcmd "$MOCKCMD --rebuild ${TESTDIR}/test-C-1.1-0.src.rpm --resultdir $TMPDIR" \
    || die "mock rebuild failed"

rpmoutput=$(rpm --qf '%{NAME} %{RSAHEADER}\n' -qp "$TMPDIR"/*.rpm 2>/dev/null)
lines=0
while read -r line; do
    case $line in
        "(none)") die "some packages are not signed" ;;
        *)
            if test ${#line} -lt 256; then
                die "weird signature $line"
            fi
            ;;
    esac
    lines=$(( lines + 1 ))
done <<<"$rpmoutput"

test $lines -eq 2 || die "two packages are expected to be signed"

exit 0
