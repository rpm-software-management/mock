#! /bin/bash

PREPAREDIR=$(dirname "$(readlink -f "$0")")
cd "$PREPAREDIR" || exit 1
. "$PREPAREDIR/functions"

ask_yes "This is going to DESTRUCTIVELY configure this BOX, " \
        "Do you want to continue?" || die "-> stopped"

user=$(id -u -n)
test "$user" != root || die "run this as normal user with sudo access"

set -e

sudo dnf install -y \
    make \
    mock \
    mock-lvm \
    nosync.x86_64 nosync.i686 \
    podman \
    rpm-sign \
    tito

sudo usermod -a -G mock "$user"

"$PREPAREDIR/prepare-user.sh"

sudo "$PREPAREDIR/prepare-lvm.sh"
