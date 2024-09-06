This version addresses [issue#521][], which requested a cleanup option for
all chroots.  A [new][PR#1337] option, `--scrub-all-chroots`, has been
added.  It can detect leftovers in `/var/lib/mock` or `/var/cache/mock`
and make multiple `mock --scrub=all` calls accordingly.
