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

$(bin_PROGRAMS): src/libselinux-mock.la
$(EXTRA_PROGRAMS): src/libselinux-mock.la
CLEANFILES += $(EXTRA_PROGRAMS)

AM_CPPFLAGS = -I$(top_builddir)/src -I$(top_srcdir)/src

lib_LTLIBRARIES = src/libselinux-mock.la
src_libselinux_mock_la_LDFLAGS = -version-info $(MOCK_LIBTOOL_CURRENT):$(MOCK_LIBTOOL_REVISION):$(MOCK_LIBTOOL_AGE)
src_libselinux_mock_la_CFLAGS = 
src_libselinux_mock_la_SOURCES = src/selinux-mock.c

bin_PROGRAMS += src/mock
src_mock_SOURCES = src/mock.c
src_mock_LDFLAGS =

dist_libexec_SCRIPTS = src/mock.py
man_MANS = docs/mock.1

src/mock.py: configure.ac Makefile.am
	echo Updating $@, current pwd: $$(pwd)
	cp -f $(top_srcdir)/$@ $(top_builddir)/$@.new
	perl -p -i -e 's/^__VERSION__=.*/__VERSION__="$(RELEASE_VERSION)"/' $(top_builddir)/$@.new
	diff -q $(top_srcdir)/$@ $(top_builddir)/$@.new >/dev/null 2>&1 || mv -f $(top_builddir)/$@.new $(top_builddir)/$@
	rm -f $(top_builddir)/$@.new
	chmod +x $(top_builddir)/$@ || :

EXTRA_DIST += etc docs src/mock-yum buildsys-build.spec

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

