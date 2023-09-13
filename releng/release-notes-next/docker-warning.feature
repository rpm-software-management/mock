There's a [new "INFO" message][commit#8c7aad5680e8f86] raised when running
Podman in Docker, potentially without `docker run --privileged`.  This should
decrease the confusion if Mock subsequently falls-back to non-default
`use_bootstrap_image=False`.  See [issue#1184][] for more info.
