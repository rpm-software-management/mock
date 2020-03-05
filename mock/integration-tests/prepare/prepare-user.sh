#! /bin/bash

ask_yes() {
    read -p "$* [y/N] " -n 1 -r
    echo
    case $REPLY in
        y|Y) true  ;;
        *)   false ;;
    esac
}

die()  { echo >&2 "$*"    ; exit 1 ; }
info() { echo >&2 " * $*" ; }

user=$(id -u -n)
test "$user" != root || die "don't run this as root"

ask_yes "This is going to DESTRUCTIVELY configure '$user' account." \
        "Do you want to continue?" || die "-> stopped"

# re-create workdir
workdir="$HOME/.mocktests"
rm -rf "$workdir"
mkdir -p "$workdir"


info "Prepare sign plugin"
rpmmacros=$HOME/.rpmmacros
rm -f "$rpmmacros"

gpgdir=$workdir/gpg
mkdir "$gpgdir"
chmod 0700 "$gpgdir"

# generate gpg key without password
cat > "$workdir/gpg-batch" <<EOF
%echo Generating a basic OpenPGP key
%no-protection
Key-Type: RSA
Key-Length: 4096
Name-Real: John Doe
Name-Email: jdoe@foo.com
Expire-Date: 0
Passphrase: redhat
%commit
%echo done
EOF

gpg=$workdir/gpg-mock
cat > "$gpg" <<EOF
#! /bin/sh

echo -n >&2 "running: \$0 "
for arg; do
    echo -n >&2 "\$(printf %q "\$arg") "
done
echo
exec /usr/bin/gpg --homedir "$gpgdir" "\$@"
EOF
chmod +x "$gpg"

"$gpg" --batch --generate-key "$workdir/gpg-batch"

cat > "$rpmmacros" <<EOF
# GENERATED AUTOMATICALLY by $0
# from man(8) rpmsign
%_gpg_name John Doe <jdoe@foo.com>
%__gpg $gpg
EOF
