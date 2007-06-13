SUBDIRS = etc src docs

PKGNAME = mock
VERSION=$(shell awk '/Version:/ { print $$2 }' ${PKGNAME}.spec)
RELEASE=$(shell awk '/Release:/ { print $$2 }' ${PKGNAME}.spec)

all: subdirs

clean:
	rm -f *.pyc *.pyo *~ *.bak
	for d in $(SUBDIRS); do make -C $$d clean ; done

distclean: clean
	rm -rf dist build
	rm -f *.tar.gz
	for d in $(SUBDIRS); do make -C $$d distclean ; done

subdirs:
	for d in $(SUBDIRS); do make -C $$d; [ $$? = 0 ] || exit 1 ; done

install:
	mkdir -p $(DESTDIR)/usr/bin/
	mkdir -p $(DESTDIR)/usr/libexec
	install -m 755 mock.py $(DESTDIR)/usr/bin/mock
	install -m 755 mock-yum $(DESTDIR)/usr/libexec/mock-yum
	mkdir -p $(DESTDIR)/var/lib/mock
	for d in $(SUBDIRS); do make  DESTDIR=`cd $(DESTDIR); pwd` -C $$d install; [ $$? = 0 ] || exit 1; done

EXCLUDES	:= --exclude='*~' --exclude='*.patch' --exclude='*.save' \
		   --exclude='*.rpm' --exclude='*.diff' --exclude='*.sh' \
		   --exclude='*.tar.gz' --exclude='*.tar.bz2' --exclude='*test*' \
		   --exclude='.git'
archive: clean
	@rm -rf ${PKGNAME}-*.tar.gz
	@git-archive --format=tar --prefix=${PKGNAME}-$(VERSION)/ HEAD |gzip > ${PKGNAME}-$(VERSION).tar.gz
	@echo "The archive is in ${PKGNAME}-$(VERSION).tar.gz"

rpm: archive
	rm -rf build dist
	mkdir build dist
	rpmbuild --define "_sourcedir $(PWD)" --define "_builddir $(PWD)/build" --define "_srcrpmdir $(PWD)/dist" --define "_rpmdir $(PWD)/dist" -ba mock.spec

RPMARGS 	:= --define "_sourcedir $(PWD)" \
		   --define "_builddir $(PWD)/buildsys" \
		   --define "_srcrpmdir $(PWD)/buildsys" \
		   --define "_rpmdir $(PWD)/buildsys" 

buildsys-rpm:
	rm -rf buildsys
	mkdir buildsys
	for i in 1 2 3 4 5 6; do \
		rpmbuild $(RPMARGS) --define "fedora $$i" --define "dist .fc$$i" -bb buildsys-build.spec; \
	done
	for i in 3 4 5; do \
		rpmbuild $(RPMARGS) --define "rhel $$i" --define "dist .el$$i" -bb buildsys-build.spec; \
	done
	for i in 73 8 9; do \
		rpmbuild $(RPMARGS) --define "rhl $$i" --define "dist .rh$$i" -bb buildsys-build.spec; \
	done
	rpmbuild $(RPMARGS) --define "fedora development" --define "dist .fc7" -bb buildsys-build.spec
