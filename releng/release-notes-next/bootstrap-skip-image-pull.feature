There's a new `config_opts['bootstrap_image_skip_pull']` option that allows you
to skip image pulling (running the `podman pull` command by Mock) when preparing
the bootstrap chroot.  This is useful if `podman pull` is failing, for example,
when the registry is temporarily or permanently unavailable, but the local image
exists, or if the image reference is pointing at a local-only image.
