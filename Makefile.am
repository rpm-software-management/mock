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

LIBTOOL_CURRENT=@LIBTOOL_CURRENT@
LIBTOOL_REVISION=@LIBTOOL_REVISION@
LIBTOOL_AGE=@LIBTOOL_AGE@

CLEANFILES=mock-*.tar.gz mock-*.tar.bz2 mock-*.rpm _buildtemp version
DISTCLEANFILES=*~

EXTRA_DIST =
bin_PROGRAMS=
CLEANFILES += $(EXTRA_PROGRAMS)

mocketcdir = $(sysconfdir)/mock
dist_mocketc_DATA = $(wildcard $(top_srcdir)/etc/mock/*.cfg) $(top_srcdir)/etc/mock/logging.ini

EXTRA_DIST += docs buildsys-build.spec-template mock.spec
sbin_SCRIPTS = py/mock.py
man_MANS = docs/mock.1

pamdir = $(sysconfdir)/pam.d/
pam_DATA = etc/pam/mock

consoledir = $(sysconfdir)/security/console.apps/
console_DATA = etc/consolehelper/mock

pluginsdir = $(pkgpythondir)/plugins
plugins_PYTHON = \
 	py/mock/plugins/bind_mount.py \
 	py/mock/plugins/ccache.py \
	py/mock/plugins/root_cache.py 	\
	py/mock/plugins/yum_cache.py

pkgpython_PYTHON = \
	py/mock/__init__.py 	\
	py/mock/exception.py 	\
	py/mock/util.py 		\
	py/mock/backend.py		\
	py/mock/trace_decorator.py  \
	py/mock/uid.py 

CLEANFILES += py/*.pyc py/mock/*.pyc py/mock/plugins/*.pyc

REPLACE_VARS_ON_INSTALL=$(sbindir)/mock
install-exec-hook:
	for i in $(REPLACE_VARS_ON_INSTALL); do      \
		file=$(DESTDIR)/$$i			;\
                perl -p -i -e 's|^__VERSION__ =.*|__VERSION__="$(RELEASE_VERSION)"|' $$file ;\
                perl -p -i -e 's|^SYSCONFDIR =.*|SYSCONFDIR="$(sysconfdir)"|' $$file        ;\
                perl -p -i -e 's|^PYTHONDIR =.*|PYTHONDIR="$(pythondir)"|' $$file           ;\
                perl -p -i -e 's|^PKGPYTHONDIR =.*|PKGPYTHONDIR="$(pkgpythondir)"|' $$file  ;\
                perl -p -i -e 's|^PKGDATADIR =.*|PKGDATADIR="$(pkgdatadir)"|' $$file        ;\
                perl -p -i -e 's|^LIBDIR =.*|PKGDATADIR="$(libdir)"|' $$file        ;\
        done

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

.PHONY: rpm srpm
rpm: dist
	mkdir -p $(BUILDDIR)
	rpmbuild $(RPM_DEFINES) -ba --nodeps $(PACKAGE_NAME).spec
	rm -rf $(BUILDDIR)

srpm: dist
	mkdir -p $(BUILDDIR)
	rpmbuild $(RPM_DEFINES) -ba --nodeps $(PACKAGE_NAME).spec
	rm -rf $(BUILDDIR)
