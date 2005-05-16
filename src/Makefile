CC=gcc
EXECUTABLE=mock-helper
SBINDIR=/usr/sbin
MOCKGROUP=mock
DESTDIR=''
INSTALL=/usr/bin/install
MKDIR=/bin/mkdir
all: 
	$(CC) -o $(EXECUTABLE) mock-helper.c 

clean:
	rm -f $(EXECUTABLE)
	rm -f *~ *.bak

install:
	$(MKDIR) -p $(DESTDIR)/$(SBINDIR)
	$(INSTALL) -m 4750 $(EXECUTABLE) $(DESTDIR)/$(PKGDIR)/$(SBINDIR)/$(EXECUTABLE)

