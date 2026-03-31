Mock now decodes percent-escaped local `file://` repository paths before
checking them for bootstrap bind mounts. This fixes bootstrap package-manager
access to host-local repositories whose paths contain characters such as `@`
and therefore appear escaped in file URIs, as in [PR#1728][].
