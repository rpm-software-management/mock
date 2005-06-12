all:
	echo "Nothing to do"

clean:
	rm -f *.bak *~

install:
	mkdir -p $(DESTDIR)/etc/mock/
	for item in *.cfg; do \
		install -m 644 $$item $(DESTDIR)/etc/mock/$$item; \
	done
	for arch in i386 ppc x86_64 ; do \
		ln -sv fedora-5-$$arch-core.cfg  $(DESTDIR)/etc/mock/fedora-development-$$arch-core.cfg; \
	done

