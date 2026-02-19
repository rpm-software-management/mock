Image has one Digest and many RepoDigests. So, we can hit situation when these
two values don't match and podman will refuse to load such tarball later with
error like described [here](https://github.com/containers/podman/issues/27323).

We should move to different mechanism (probably skopeo) in the near future.
