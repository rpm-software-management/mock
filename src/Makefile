CC=gcc
EXECUTABLE=mock-helper
SBINDIR=/usr/sbin
MOCKGROUP=mock
DESTDIR=''
INSTALL=/usr/bin/install
MKDIR=/bin/mkdir

ifndef NOSELINUX
SELINUXFLAGS=-DUSE_SELINUX=1 -lselinux
endif

ifneq (,$(filter ppc64 x86_64 s390x,$(shell uname -m)))
LIBDIR = /usr/lib64
else
LIBDIR = /usr/lib
endif

all: 
	$(CC) $(CFLAGS) -o $(EXECUTABLE) mock-helper.c $(SELINUXFLAGS)
	$(CC) $(CFLAGS) -fPIC -c selinux-mock.c
	$(LD) -shared -o libselinux-mock.so selinux-mock.o

clean:
	rm -f $(EXECUTABLE)
	rm -f *~ *.bak *.o *.so

install:
	$(MKDIR) -p $(DESTDIR)/$(SBINDIR) $(DESTDIR)/$(LIBDIR)
	$(INSTALL) -m 4750 $(EXECUTABLE) $(DESTDIR)/$(SBINDIR)/$(EXECUTABLE)
	$(INSTALL) -m 755 libselinux-mock.so $(DESTDIR)/$(LIBDIR)

