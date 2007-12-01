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

MOCK_LIBTOOL_CURRENT=@MOCK_LIBTOOL_CURRENT@
MOCK_LIBTOOL_REVISION=@MOCK_LIBTOOL_REVISION@
MOCK_LIBTOOL_AGE=@MOCK_LIBTOOL_AGE@

CLEANFILES=mock-*.tar.gz mock-*.tar.bz2 mock-*.rpm _buildtemp version
DISTCLEANFILES=*~

EXTRA_DIST =
bin_PROGRAMS=
check_PROGRAMS= src/daemontest
#TESTS = docs/make_check.sh

CLEANFILES += $(EXTRA_PROGRAMS)

AM_CFLAGS = -Wall -I$(top_srcdir)/src -DSYSCONFDIR='"$(sysconfdir)"' -DLIBEXECDIR='"$(libexecdir)"' -DLIBDIR='"$(libdir)"' -Werror

bin_PROGRAMS += src/mock
src_mock_SOURCES = src/mock.c
src_mock_LDFLAGS =

mocketcdir = $(sysconfdir)/mock
dist_mocketc_DATA = $(wildcard $(top_srcdir)/etc/mock/*.cfg) $(top_srcdir)/etc/mock/logging.ini

EXTRA_DIST += docs buildsys-build.spec-template mock.spec
dist_libexec_SCRIPTS = py/mock.py
man_MANS = docs/mock.1

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
	py/mock/decorator.py 	\
	py/mock/trace_decorator.py  \
	py/mock/uid.py 

CLEANFILES += py/*.pyc py/mock/*.pyc py/mock/plugins/*.pyc

REPLACE_VARS_ON_INSTALL=$(libexecdir)/mock.py
install-exec-hook:
	for i in $(REPLACE_VARS_ON_INSTALL); do      \
		file=$(DESTDIR)/$$i			;\
                perl -p -i -e 's|^__VERSION__=.*|__VERSION__="$(RELEASE_VERSION)"|' $$file ;\
                perl -p -i -e 's|^SYSCONFDIR=.*|SYSCONFDIR="$(sysconfdir)"|' $$file        ;\
                perl -p -i -e 's|^PYTHONDIR=.*|PYTHONDIR="$(pythondir)"|' $$file           ;\
                perl -p -i -e 's|^PKGPYTHONDIR=.*|PKGPYTHONDIR="$(pkgpythondir)"|' $$file  ;\
                perl -p -i -e 's|^PKGDATADIR=.*|PKGDATADIR="$(pkgdatadir)"|' $$file        ;\
        done

.PHONY: rpm srpm
rpm: dist
	BLD_DIR=$$(mktemp -d /tmp/rpmbuild-$$$$-XXXXXX); \
	mkdir -p $$BLD_DIR/SOURCES $$BLD_DIR/BUILD $$BLD_DIR/RPMS $$BLD_DIR/RPMS/i386 $$BLD_DIR/RPMS/noarch $$BLD_DIR/SRPMS $$BLD_DIR/SPECS ;\
	rpmbuild --define "_topdir $$BLD_DIR" -ta --nodeps $(RELEASE_STRING).tar.gz  ;\
	cp $$BLD_DIR/SRPMS/*rpm .       ;\
	cp $$BLD_DIR/RPMS/*/*rpm .       ;\
	rm -rf $$BLD_DIR

srpm: dist
	BLD_DIR=$$(mktemp -d /tmp/rpmbuild-$$$$-XXXXXX); \
	mkdir -p $$BLD_DIR/SOURCES $$BLD_DIR/BUILD $$BLD_DIR/RPMS $$BLD_DIR/RPMS/i386 $$BLD_DIR/RPMS/noarch $$BLD_DIR/SRPMS $$BLD_DIR/SPECS ;\
	rpmbuild --define "_topdir $$BLD_DIR" -ts --nodeps $(RELEASE_STRING).tar.gz  ;\
	cp $$BLD_DIR/SRPMS/*rpm .       ;\
	rm -rf $$BLD_DIR

