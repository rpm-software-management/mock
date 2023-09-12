Mock now, at least on the best effort basis (if used with
`package_manager=dnf`), ["fails" with exit status 30][issue#42] if it isn't able
to process the `--postinstall` request (ie. installing the built packages into
the target chroot).  Previous Mock versions used to ignore (with warning) the
failed package installation attempts.
