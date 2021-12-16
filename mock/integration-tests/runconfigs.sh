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
    configs=$(ls ../mock-core-configs/etc/mock | grep .cfg \
                | grep -v -e default -e custom -e chroot-aliases \
                | grep -E -v 'arm|ppc|s390|sparc|aarch')
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
    # Keep building the SIMPLESRPM
    # - oraclelinux+epel can't work with mock.spec, as %rhel is not defined
    # - fedora-eln doesn't provide all the EPEL packages needed by mock.spec
    oraclelinux+epel-7*) ;;
    fedora-eln*) ;;
    # For EPEL/Fedora try to build Mock.
    fedora*|*+epel*-[78]*)
        # we support building mock there, so test it instead
        srpm=$MOCKSRPM
        ;;
    # Skip tests for those chroots.
    # - amazonlinux - see #522
    amazonlinux*) continue;;
    esac

    # For branched Fedoras, try also updates-testing.
    target_config=$(basename "$(readlink -f "../mock-core-configs/etc/mock/$i")")
    enablerepo=
    case $target_config in
    fedora-eln*|fedora-rawhide*|fedora*i*86*) ;;
    fedora*)
        enablerepo=" --enablerepo updates-testing " ;;
    esac

    name=$(basename $i .cfg)
    header "testing config $name.cfg with tmpfs plugin"
    runcmd "$MOCKCMD -r $name --enable-plugin=tmpfs --rebuild $srpm $enablerepo"
    if [ $? != 0 ]; then
        echo "FAILED: $i (tmpfs)"
        fails=$(($fails+1))
    else
        echo "PASSED: $i (tmpfs)"
    fi
    sudo python ${TESTDIR}/dropcache.py
    header "testing config $name.cfg *without* tmpfs plugin"
    runcmd "$MOCKCMD -r $name --disable-plugin=tmpfs --rebuild $srpm $enablerepo"
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
