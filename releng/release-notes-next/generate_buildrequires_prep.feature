Only run the `%prep` section once when running `%generate_buildrequires`
multiple times.
Previously Mock run `%prep` repeatedly before each `%generate_buildrequires`
round except for the last one.
This was inconsistent and unnecessary slow/wasteful.

When the original support for `%generate_buildrequires` landed into Mock,
the intention was to only call `%prep` once.
However when Mock added support for multiple rounds of
`%generate_buildrequires`, `%prep` ended up only being skipped in the final
`rpmbuild` call. This was an oversight.
`%prep` is now only called once, as originally intended.

Some RPM packages might be affected by the change, especially if a dirty
working directory after running `%generate_buildrequires` affects the results
of subsequent rounds of `%generate_buildrequires`.
However, such behavior was undefined and quite buggy even previously,
due to the lack of the `%prep` section in the final `rpmbuild` call.

Packages that need to run commands before every round of
`%generate_buildrequires` should place those commands in
the `%generate_buildrequires` section itself rather than `%prep`.
