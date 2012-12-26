#!/bin/sh

cfgs=$(grep 'mirrorlist' ../etc/mock/*.cfg | sed -e 's/^.*mirrorlist=//')
tmpfile=$(mktemp)
for c in $cfgs; do
    wget -q -O $tmpfile $c
    lines=$(wc -l $tmpfile | awk '{print $1}')
    if [ $lines = 1 ]; then
	echo "!!! $c is not a valid URL!!!"
    fi
done
