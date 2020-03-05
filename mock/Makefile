# vim:noexpandtab:autoindent:tabstop=8:shiftwidth=8:filetype=make:nocindent:tw=0:
check:
	./integration-tests/runtests.sh

AUTHORS:
	(GIT_DIR=.git git log | grep ^Author | sort |uniq > .authors.tmp && mv .authors.tmp AUTHORS; rm -f .authors.tmp) || (touch AUTHORS; echo 'git directory not found: installing possibly empty AUTHORS.' >&2)

install-exec-hook:
	for i in $(REPLACE_VARS_ON_INSTALL); do      \
		file=$(DESTDIR)/$$i			;\
                perl -p -i -e 's|^__VERSION__\s*=.*|__VERSION__="$(RELEASE_VERSION)"|' $$file ;\
                perl -p -i -e 's|^SYSCONFDIR\s*=.*|SYSCONFDIR="$(sysconfdir)"|' $$file        ;\
                perl -p -i -e 's|^PYTHONDIR\s*=.*|PYTHONDIR="$(pythondir)"|' $$file           ;\
                perl -p -i -e 's|^PKGPYTHONDIR\s*=.*|PKGPYTHONDIR="$(mockbuilddir)"|' $$file  ;\
                perl -p -i -e 's|^PKGDATADIR\s*=.*|PKGDATADIR="$(pkgdatadir)"|' $$file        ;\
                perl -p -i -e 's|^LIBDIR\s*=.*|LIBDIR="$(libdir)"|' $$file        ;\
        done
	mv $(DESTDIR)/$(sbindir)/mock.py $(DESTDIR)/$(sbindir)/mock
	[ -d $(DESTDIR)/$(bindir) ] || mkdir $(DESTDIR)/$(bindir)
	mv $(DESTDIR)/$(sbindir)/mockchain.py $(DESTDIR)/$(bindir)/mockchain


.PHONY: rpm srpm help install-devel-packages
rpm:
	tito build --test --rpm

srpm:
	tito build --test --srpm

install-devel-packages:
	yum --disablerepo='beaker*' install mock rpm-build fedora-packager vim-enhanced git-all

help:
	@echo
	@echo "Mock Makefile targets:"
	@echo "	dist	- generate Authors file"
	@echo "	rpm	- build binary RPM"
	@echo "	srpm	- build source RPM"
	@echo "	help	- print this message"
	@echo "Additionally, all standard automake targets are supported"
	@echo

# Tell versions [3.59,3.63) of GNU make to not export all variables.
# Otherwise a system limit (for SysV at least) may be exceeded.
.NOEXPORT:
