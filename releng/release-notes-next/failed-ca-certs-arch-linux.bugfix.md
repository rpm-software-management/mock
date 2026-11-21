Fix the problem of copying host SSL ca-bundle to chroot in host file systems
where `tls-ca-bundle` is not located in `/etc/pki`.
For that purpose, we add `/etc/ca-certificates/extracted/tls-ca-bundle.pem`
as an alternative location of the host ca bundle to be tested for copying
into the chroot.

See, [issue#1828][] and [PR#1840][].
