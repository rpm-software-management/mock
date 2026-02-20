Bootstrap image caching for hermetic builds now use
[skopeo](https://github.com/containers/skopeo) sync instead of ``podman
pull|save`` commands. Skopeo better handles digests, so we can always be sure
that we're using correct image.
