SUBDIRS = etc src docs

PKGNAME = mock
VERSION=$(shell awk '/Version:/ { print $$2 }' ${PKGNAME}.spec)
RELEASE=$(shell awk '/Release:/ { print $$2 }' ${PKGNAME}.spec)
CVSTAG=mock-$(subst .,_,$(VERSION)-$(RELEASE))

all: subdirs

clean:
	rm -f *.pyc *.pyo *~ *.bak
	for d in $(SUBDIRS); do make -C $$d clean ; done

distclean: clean
	rm -rf dist build
	rm *.tar.gz

subdirs:
	for d in $(SUBDIRS); do make -C $$d; [ $$? = 0 ] || exit 1 ; done

install:
	mkdir -p $(DESTDIR)/usr/bin/
	mkdir -p $(DESTDIR)/usr/libexec
	install -m 755 mock.py $(DESTDIR)/usr/bin/mock
	install -m 755 mock-yum $(DESTDIR)/usr/libexec/mock-yum
	mkdir -p $(DESTDIR)/var/lib/mock
	for d in $(SUBDIRS); do make  DESTDIR=`cd $(DESTDIR); pwd` -C $$d install; [ $$? = 0 ] || exit 1; done

archive:
	@rm -rf ${PKGNAME}-%{VERSION}.tar.gz
	@rm -rf /tmp/${PKGNAME}-$(VERSION) /tmp/${PKGNAME}
	@dir=$$PWD; cd /tmp; cp -a $$dir ${PKGNAME}
	@rm -rf /tmp/${PKGNAME}/${PKGNAME}-daily.spec /tmp/${PKGNAME}/build /tmp/${PKGNAME}/dist
	@mv /tmp/${PKGNAME} /tmp/${PKGNAME}-$(VERSION)
	@dir=$$PWD; cd /tmp; tar cvz --exclude=CVS --exclude=.cvsignore -f $$dir/${PKGNAME}-$(VERSION).tar.gz ${PKGNAME}-$(VERSION)
	@rm -rf /tmp/${PKGNAME}-$(VERSION)	
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
	for i in 3 4; do \
		rpmbuild $(RPMARGS) --define "el $$i" --define "dist .el$$i" -bb buildsys-build.spec; \
	done
	for i in 73 8 9; do \
		rpmbuild $(RPMARGS) --define "rhl $$i" --define "dist .rh$$i" -bb buildsys-build.spec; \
	done
