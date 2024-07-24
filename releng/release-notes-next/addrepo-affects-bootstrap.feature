The `--addrepo` option has been updated to affect both the bootstrap chroot
installation and the buildroot installation, as requested in [issue#1414][].
However, be cautious, as Mock [aggressively caches the bootstrap][issue#1289].
Always remember to run `mock -r <chroot> --scrub=bootstrap` first.
Additionally, as more chroots are being switched to `bootstrap_image_ready =
True`, you'll likely need to use `--addrepo` **in combination with**
`--no-bootstrap-image`; otherwise, the bootstrap chroot installation will remain
unaffected.
