#! /bin/bash

## Prepare templates for the next branched Fedora verasion
##
## E.g. when the Fedora Rawhide is going to be branched into Fedora 35,
## execute this script as './releng/rawhide-branching.sh' (without
## arguments).

set -e
topdir=$(git rev-parse --show-toplevel)

cd "$topdir/mock-core-configs/etc/mock"

for config in fedora-??-x86_64.cfg; do
    prev_version=$version
    version=$(echo "$config" | sed -e 's/fedora-//' -e 's/-x86_64.*//')
    next_version=$(( version + 1 ))
done

architectures=()
for config in fedora-"$version"-*.cfg; do
    architecture=$(echo "$config" | sed -e "s/fedora-$version-//" -e "s/.cfg//")
    architectures+=( "$architecture" )
done

echo "Set:    rawhide == Fedora $next_version"
echo "Move:   $prev_version => $version"
echo "Arches: ${architectures[*]}"

for arch in "${architectures[@]}"; do
    # drop the old rawhide symlink
    rm "fedora-$version-$arch.cfg"
    # copy old branched config to new branched config, and update releasever
    cp fedora-{"$prev_version","$version"}-"$arch.cfg"
    sed -i "s|'$prev_version'|'$version'|" "fedora-$version-$arch.cfg"
    # create updated rawhide symlink
    ln -s "fedora-rawhide-$arch.cfg" "fedora-$next_version-$arch.cfg"
    # stash those updated configs
    git add "fedora-$next_version-$arch.cfg" "fedora-$version-$arch.cfg"
done

towncrier_file=$topdir/releng/release-notes-next/fedora-$version-branching.feature
cat > "$towncrier_file" <<EOF
Configuration files for Fedora $version have been branched from Rawhide,
according to the [Fedora $version Schedule](https://fedorapeople.org/groups/schedule/f-$version/f-$version-all-tasks.html).
EOF
git add "$towncrier_file"

# Use updated relasever in rawhide template, because we need to reference
# updated GPG keys (of $next_version and $versiono).

for file in templates/fedora-rawhide.tpl templates/fedora-eln.tpl; do
  sed -i "s|'$version'|'$next_version'|" "$file"
  git add "$file"
done


config_spec=$topdir/mock-core-configs/mock-core-configs.spec
sed -i "s/\(Version:[[:space:]]\+\).*/\1$version.0.post1/" "$config_spec"
git add "$config_spec"

echo "WARNING: Make sure Fedora Copr maintainers are informed that"
echo "WARNING: they should run 'copr-frontend branch-fedora $version'".
echo "WARNING: That has to be done right on time when branching is done."
echo "WARNING: Please check that distribution-gpg-keys have the N+1 key,"
echo "         you likely want to bump Requires: distribution-gpg-keys!"
