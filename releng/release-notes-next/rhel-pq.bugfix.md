RHEL 10.1 and RHEL9.7 now uses Post-Quantum (PQ) GPG keys. This release adds these keys to the RHEL 9 configs.
Unfortunately, RPM on Fedoras and other systems cannot handle PQ keys and fails to import them.
Therefore you need to either use a bootstrap-image or run Mock on RHEL 10.1+ or RHEL9.7+.
