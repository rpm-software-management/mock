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
EXTRA_PROGRAMS=

CLEANFILES += $(EXTRA_PROGRAMS)

AM_CFLAGS = -Wall -I$(top_srcdir)/src -DSYSCONFDIR='"$(sysconfdir)"' -DLIBEXECDIR='"$(libexecdir)"' -DLIBDIR='"$(libdir)"' -Werror

bin_PROGRAMS += src/mock
src_mock_SOURCES = src/mock.c
src_mock_LDFLAGS =

mocketcdir = $(sysconfdir)/mock
dist_mocketc_DATA = $(wildcard $(top_srcdir)/etc/*.cfg) $(top_srcdir)/etc/logging.ini

EXTRA_DIST += docs buildsys-build.spec-template mock.spec
dist_libexec_SCRIPTS = src/mock.py
man_MANS = docs/mock.1

pluginsdir = $(pkgpythondir)/plugins
plugins_PYTHON = \
 	src/py-libs/plugins/bind_mount.py \
 	src/py-libs/plugins/ccache.py \
	src/py-libs/plugins/root_cache.py 	\
	src/py-libs/plugins/yum_cache.py

pkgpython_PYTHON = \
	src/py-libs/__init__.py 	\
	src/py-libs/exception.py 	\
	src/py-libs/util.py 		\
	src/py-libs/backend.py		\
	src/py-libs/decorator.py 	\
	src/py-libs/trace_decorator.py 	\
	src/py-libs/uid.py

if BLD_SRC_DIFFERENT
 $(top_builddir)/src/mock.py: $(top_srcdir)/src/mock.py
 CLEANFILES+=$(top_builddir)/src/mock.py
endif

src/mock.py: Makefile
	echo Updating $@, current pwd: $$(pwd)
	cp -f $(top_srcdir)/src/mock.py $(top_builddir)/src/mock.py.new
	perl -p -i -e 's|^__VERSION__=.*|__VERSION__="$(RELEASE_VERSION)"|' $(top_builddir)/src/mock.py.new
	perl -p -i -e 's|^SYSCONFDIR=.*|SYSCONFDIR="$(sysconfdir)"|' $(top_builddir)/src/mock.py.new
	perl -p -i -e 's|^PYTHONDIR=.*|PYTHONDIR="$(pythondir)"|' $(top_builddir)/src/mock.py.new
	perl -p -i -e 's|^PKGPYTHONDIR=.*|PKGPYTHONDIR="$(pkgpythondir)"|' $(top_builddir)/src/mock.py.new
	diff -q $(top_srcdir)/src/mock.py $(top_builddir)/src/mock.py.new >/dev/null 2>&1 || mv -f $(top_builddir)/src/mock.py.new $(top_builddir)/src/mock.py
	rm -f $(top_builddir)/src/mock.py.new
	chmod +x $(top_builddir)/src/mock.py 2>/dev/null || :

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

