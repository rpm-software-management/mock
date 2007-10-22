all:
	echo "Nothing to do"

clean:
	rm -f *.bak *~

distclean: clean

install:
	mkdir -p $(DESTDIR)/etc/mock/
	for item in *.cfg; do \
		install -m 644 $$item $(DESTDIR)/etc/mock/$$item; \
	done
