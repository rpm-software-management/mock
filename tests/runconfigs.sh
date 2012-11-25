#!/bin/sh

if [ "$MOCKCMD" = "" ]
then
    d=$(cd $(dirname $0); pwd)
    source $d/testenvironment
fi

source ${TESTDIR}/functions

cd $TOPDIR

if [ "$1" != "" ]; then
    configs=$1
else
    excludes='arm|ppc|s390|sparc'
    arch=$(uname -m)
    echo "host arch: $arch"
    if [ "$arch" != "x86_64" ]
    then 
	excludes="$excludes|x86_64"
    fi
    configs=$(ls etc/mock | grep .cfg | grep -v default | egrep -v $excludes)
fi

trap '$MOCKCMD --clean; exit 1' INT HUP QUIT TERM

fails=0

#
# Test build all configs we ship.
#
header "testing all supported configurations"
for i in $configs; do
    name=$(basename $i .cfg)
    MOCKCMD="sudo ./py/mock.py $VERBOSE --resultdir=$outdir --uniqueext=$uniqueext -r $name $MOCK_EXTRA_ARGS"
    if [ "${i#epel-4-x86_64.cfg}" != "" ]; then
	header "testing config $name.cfg with tmpfs plugin"
	runcmd "$MOCKCMD --enable-plugin=tmpfs --rebuild $MOCKSRPM "
	if [ $? != 0 ]; then 
	    echo "FAILED!"
	    fails=$(($fails+1))
	else
	    echo "PASSED!"
	fi
	sudo python ${TESTDIR}/dropcache.py
    fi
    header "testing config $name.cfg *without* tmpfs plugin"
    runcmd "$MOCKCMD                       --rebuild $MOCKSRPM"
    if [ $? != 0 ]; then 
	echo "FAILED!"
	fails=$(($fails+1))
    else
	echo "PASSED!"
    fi
done

msg=$(printf "%d configuration failures\n" $fails)
header "$msg"
exit $fails
