#! /bin/bash

die()  { echo >&2 "$*"    ; exit 1 ; }

set -x
set -e

test "$(id -u -n)" = root || die "this needs to be run as root"

filename=/test-lvm-disk

if test -f "$filename"; then
    die "file $filename already exists, did you run this script before?"
fi

dd if=/dev/zero of="$filename" bs=1M count=8000
device=$(losetup -f "$filename" --show)
pvcreate "$device"
vgcreate mock "$device"
