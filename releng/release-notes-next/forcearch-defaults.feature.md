Mock now automatically maps the target build architecture directly to the
appropriate QEMU user-static binary variant for `forcearch` builds.  For
example, a build for `riscv64` (for `fedora-43-riscv64` target) is mapped to
`/usr/bin/qemu-riscv64-static` (see the architecture string matches).  Mock
config contributors no longer need to modify Mock code to add support for new
architectures (if these architecture specifiers match).
