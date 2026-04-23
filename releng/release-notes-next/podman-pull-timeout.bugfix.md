Podman image pull now has a per-attempt timeout (configurable via
`bootstrap_image_pull_timeout` and `buildroot_image_pull_timeout`, default
120 seconds) to prevent indefinite hangs and allow the retry logic to work.
