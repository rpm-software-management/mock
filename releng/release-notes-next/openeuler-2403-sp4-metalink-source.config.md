Update openEuler 24.03 LTS chroot to SP4 and fix the source and
update-source metalink repositories across all openEuler templates
(20.03, 22.03, 24.03): the `path=` metalink form does not translate the
`$releasever` dnf variable into the full mirror directory name, so it
resolved to a non-existent path and silently broke `mock --sources`.
