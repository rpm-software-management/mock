Probe if systemd-nspawn has the --restrict-address-families option
and use it if available. Otherwise, systemd-nspawn will print a warning
about planned changes to its default behaviour in a future version
and urge to use said option ([issue#1799][]). This pollutes mock's
output, breaking other tools, like fedora-review ([rhbz#2511998][]).
