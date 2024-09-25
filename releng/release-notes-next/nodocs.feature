Config files that uses DNF now contains `tsflags=nodocs` that tells RPM to not
install documentation files.
This results to smaller buildroot. For fedora-rawhide, with only minimal set of
packages, this is reduction from 260MB to 246MB.
