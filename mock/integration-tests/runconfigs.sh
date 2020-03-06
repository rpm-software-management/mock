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
    configs=$(ls ../mock-core-configs/etc/mock | grep .cfg | grep -v default | egrep -v 'arm|ppc|s390|sparc|aarch')
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
    name=$(basename $i .cfg)
    header "testing config $name.cfg with tmpfs plugin"
    runcmd "$MOCKCMD -r $name --enable-plugin=tmpfs --rebuild $MOCKSRPM "
    if [ $? != 0 ]; then
        echo "FAILED!"
        fails=$(($fails+1))
    else
        echo "PASSED!"
    fi
    sudo python ${TESTDIR}/dropcache.py
    header "testing config $name.cfg *without* tmpfs plugin"
    runcmd "$MOCKCMD -r $name --disable-plugin=tmpfs --rebuild $MOCKSRPM"
    if [ $? != 0 ]; then
	echo "FAILED!"
	fails=$(($fails+1))
    else
	echo "PASSED!"
    fi

    runcmd "$MOCKCMD -r $name --scrub=all"  || die "can not scrub"
done

msg=$(printf "%d configuration failures\n" $fails)
header "$msg"
exit $fails
