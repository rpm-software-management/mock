#!/bin/sh

if [ "$MOCKCMD" = "" ]
then
    d=$(cd $(dirname $0); pwd)
    . $d/testenvironment
fi

. ${TESTDIR}/functions

cd $TOPDIR

if [ "$1" != "" ]; then
    configs=$1
else
    configs=$(ls ../mock-core-configs/etc/mock | grep .cfg | grep -v -e default -e custom | egrep -v 'arm|ppc|s390|sparc|aarch')
fi

cleanup()
{
    $MOCKCMD --clean
    $MOCKCMD --scrub bootstrap
    exit 1
}
trap cleanup INT HUP QUIT TERM

fails=0

#
# Test build all configs we ship.
#
header "testing all supported configurations"
for i in $configs; do
    srpm=$SIMPLESRPM
    case $i in
    fedora-eln*) continue ;;
    amazonlinux*) continue;;
    fedora*|epel-[78]*|rhelepel-[78]*)
        # we support building mock there, so test it instead
        srpm=$MOCKSRPM
        ;;
    esac

    name=$(basename $i .cfg)
    header "testing config $name.cfg with tmpfs plugin"
    runcmd "$MOCKCMD -r $name --enable-plugin=tmpfs --rebuild $srpm "
    if [ $? != 0 ]; then
        echo "FAILED: $i (tmpfs)"
        fails=$(($fails+1))
    else
        echo "PASSED: $i (tmpfs)"
    fi
    sudo python ${TESTDIR}/dropcache.py
    header "testing config $name.cfg *without* tmpfs plugin"
    runcmd "$MOCKCMD -r $name --disable-plugin=tmpfs --rebuild $srpm "
    if [ $? != 0 ]; then
	echo "FAILED: $i"
	fails=$(($fails+1))
    else
	echo "PASSED: $i"
    fi

    runcmd "$MOCKCMD -r $name --scrub=all"  || die "can not scrub"
done

msg=$(printf "%d configuration failures\n" $fails)
header "$msg"
exit $fails
