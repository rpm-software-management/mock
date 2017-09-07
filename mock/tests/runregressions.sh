#!/bin/sh


if [ "$MOCKCMD" = "" ]
then
    d=$(cd $(dirname $0); pwd)
    . $d/testenvironment
fi

. ${TESTDIR}/functions

cd $TOPDIR

trap '$MOCKCMD --clean; exit 1' INT HUP QUIT TERM

$MOCKCMD --init

fails=0
#
# run regression tests
#
header "running regression tests"
for i in ${TESTDIR}/*.tst; do
    sh $i
    if [ $? != 0 ]; then
	fails=$(($fails + 1))
	echo "*  FAILED: $i"
    else
	echo "*  PASSED: $i"
    fi
    echo "****************************************************"
done

msg=$(printf "%d regression failures\n" $fails)
header "$msg"

#
# clean up
#
header "clean up from first round of tests"
runcmd "$MOCKCMD --offline --clean"

exit $fails
