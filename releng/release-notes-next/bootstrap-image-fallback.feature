We [implemented a convenience fallback][PR#1200] from **bootstrap installed from
image** to slower **bootstrap installed with host's DNF** for the cases when
Podman can not be used properly (container image can not be pulled, image can
not be mounted, image architecture mismatch, Podman is not available or not
working - e.g. if run in non-privileged Docker, etc).

There's also a new ["podman pull" backoff logic][commit#395fc07f796] that
makes Mock to retry Podman pulls for 120s by default.  Feel free to adjust this
timeout by `config_opts["bootstrap_image_keep_getting"]` option.
