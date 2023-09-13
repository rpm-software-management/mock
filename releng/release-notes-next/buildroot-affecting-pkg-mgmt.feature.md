Mock [newly logs out][PR#1210] the package management toolset versions (e.g.
version of DNF, RPM, etc.) that is used for the buildroot intallation.  This is
a feature helping users to diagnose problems with buildroot installation
(minimal buildroot, `BuildRequires`, dynamic build requires, etc.).  It might
seem like a trival addition, but sometimes it isn't quite obvious where the
tooling comes from (is that from host? from bootstrap? was it downloaded
"pre-installed" with bootstrap image?).
