# vim:noexpandtab:autoindent:tabstop=8:shiftwidth=8:filetype=make:nocindent:tw=0:

AUTOMAKE_OPTIONS = subdir-objects
SUBDIRS =

# dont move these 5 lines, as this is how we override the autoconf version and package name
RELEASE_NAME=@RELEASE_NAME@
RELEASE_MAJOR=@RELEASE_MAJOR@
RELEASE_MINOR=@RELEASE_MINOR@
RELEASE_SUBLEVEL=@RELEASE_SUBLEVEL@
RELEASE_EXTRALEVEL=@RELEASE_EXTRALEVEL@

RELEASE_VERSION = $(RELEASE_MAJOR).$(RELEASE_MINOR).$(RELEASE_SUBLEVEL)$(RELEASE_EXTRALEVEL)
RELEASE_STRING = $(RELEASE_NAME)-$(RELEASE_VERSION)
VERSION = $(RELEASE_VERSION)
PACKAGE = $(RELEASE_NAME)

CLEANFILES=mock-*.tar.gz mock-*.tar.bz2 mock-*.rpm _buildtemp version tests/daemontest
DISTCLEANFILES=*~ mock-unit-test/* x86_64/* noarch/* i386/*

TESTS=./tests/runtests.sh
$(TESTS): srpm

EXTRA_DIST = contrib
bin_PROGRAMS=
CLEANFILES += $(EXTRA_PROGRAMS)

mocketcdir = $(sysconfdir)/mock
mocketc_DATA = $(wildcard $(top_srcdir)/etc/mock/*.cfg) $(top_srcdir)/etc/mock/logging.ini

EXTRA_DIST += docs etc
dist_sbin_SCRIPTS = py/mock.py py/mockchain.py
man_MANS = docs/mock.1 docs/mockchain.1

pamdir = $(sysconfdir)/pam.d/
pam_DATA = etc/pam/mock

consoledir = $(sysconfdir)/security/console.apps/
console_DATA = etc/consolehelper/mock

bashcompdir = $(sysconfdir)/bash_completion.d/
bashcomp_DATA = etc/bash_completion.d/mock.bash

pluginsdir = $(pythondir)/mockbuild/plugins
plugins_PYTHON = \
    py/mockbuild/plugins/bind_mount.py \
    py/mockbuild/plugins/ccache.py     \
    py/mockbuild/plugins/package_state.py \
    py/mockbuild/plugins/root_cache.py \
    py/mockbuild/plugins/tmpfs.py \
    py/mockbuild/plugins/yum_cache.py \
    py/mockbuild/plugins/selinux.py   \
    py/mockbuild/plugins/mount.py

mockbuilddir = $(pythondir)/mockbuild
mockbuild_PYTHON = \
    py/mockbuild/__init__.py        \
    py/mockbuild/exception.py       \
    py/mockbuild/util.py            \
    py/mockbuild/backend.py         \
    py/mockbuild/trace_decorator.py \
    py/mockbuild/uid.py             \
    py/mockbuild/scm.py             \
    py/mockbuild/mounts.py

CLEANFILES += py/*.pyc py/mockbuild/*.pyc py/mockbuild/plugins/*.pyc

dist: ChangeLog AUTHORS
ChangeLog:
	(GIT_DIR=.git git log > .changelog.tmp && mv .changelog.tmp ChangeLog; rm -f .changelog.tmp) || (touch ChangeLog; echo 'git directory not found: installing possibly empty changelog.' >&2)

AUTHORS:
	(GIT_DIR=.git git log | grep ^Author | sort |uniq > .authors.tmp && mv .authors.tmp AUTHORS; rm -f .authors.tmp) || (touch AUTHORS; echo 'git directory not found: installing possibly empty AUTHORS.' >&2)

REPLACE_VARS_ON_INSTALL=$(sbindir)/mock.py
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

install-data-hook:
	perl -p -i -e 's|(=\s*)/etc/mock\b|$$1$(sysconfdir)/mock|' \
		$(DESTDIR)$(bashcompdir)/mock.bash

TOPDIR := $(shell cd $(top_builddir);pwd)
BUILDDIR = $(TOPDIR)/_rpmbuild
RPMDIR = $(TOPDIR)
SOURCEDIR = $(TOPDIR)
SPECDIR = $(TOPDIR)
SRCRPMDIR = $(TOPDIR)

RPM_DEFINES = --define "_topdir $(TOPDIR)" \
    --define "_builddir $(BUILDDIR)" \
    --define "_rpmdir $(RPMDIR)" \
    --define "_sourcedir $(SOURCEDIR)" \
    --define "_specdir $(SPECDIR)" \
    --define "_srcrpmdir $(SRCRPMDIR)"

RPMBUILD := $(shell if [ -e /usr/bin/rpmbuild-md5 ]; then echo rpmbuild-md5; else echo rpmbuild; fi)

.PHONY: rpm srpm help install-devel-packages
rpm: dist
	mkdir -p $(BUILDDIR)
	$(RPMBUILD) $(RPM_DEFINES) -ba --nodeps $(PACKAGE_NAME).spec
	rm -rf $(BUILDDIR)

srpm: dist
	mkdir -p $(BUILDDIR)
	$(RPMBUILD) $(RPM_DEFINES) -bs --nodeps $(PACKAGE_NAME).spec
	rm -rf $(BUILDDIR)

install-devel-packages:
	yum --disablerepo='beaker*' install mock rpm-build fedora-packager vim-enhanced git-all

help:
	@echo
	@echo "Mock Makefile targets:"
	@echo "	dist	- generate Changelog and Authors file"
	@echo "	rpm	- build binary RPM"
	@echo "	srpm	- build source RPM"
	@echo "	help	- print this message"
	@echo "Additionally, all standard automake targets are supported"
	@echo
