When a `.spec` file contains a `%generate_buildrequires` section following the
`%prep` section, the previous implementation would only initialize the
access/modification times of files belonging to installed `BuildRequires`
providers after `%generate_buildrequires`, because only then would the full set
be known.

This would cause file accesses from steps invoked in the `%prep` section to
not be detected by the plugin.

This change adds a `prebuild` hook which is called after installing the static
dependencies written in the `.spec` file but before the `%prep` section, while
still modifying the a/m-times after the final installation of both static and
dynamic dependencies.

The plugin remembers which files had their a/m-times modified and makes sure to
initialize the time of each file only once.
