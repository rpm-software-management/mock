The suggested location for the host CRT bundle is changing from
`/etc/pki/tls/certs/ca-bundle.crt` to
`/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem`, following the
[droppingOfCertPemFile Fedora Change](https://fedoraproject.org/wiki/Changes/droppingOfCertPemFile).
These bundles are automatically synced into Mock chroots for specific targets
(e.g., openSUSE).  The new bundle location is OK even for EPEL 8 hosts.
Fixes [issue#1667][].
