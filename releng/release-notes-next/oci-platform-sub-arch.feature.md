Podman container image pulls now pass `--platform` for x86_64
sub-architecture variants (x86_64_v2, x86_64_v3, x86_64_v4).  A new
`oci_platform_map` config option maps target architectures to OCI platform
strings (e.g. `linux/amd64/v2`), and the architecture check accepts
variant images on a matching base host.
