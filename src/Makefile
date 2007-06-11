CC	:=	gcc
CFLAGS 	:= 	-O2 -g -Wall -Werror
#DEBUG	:= 	-DDEBUG=1
EXECUTABLE:=	mock-helper
LIBRARY	:=	libselinux-mock.so
SBINDIR	:=	/usr/sbin
MOCKGROUP:=	mock
INSTALL	:=	/usr/bin/install
MKDIR	:=	/bin/mkdir

ifndef NOSELINUX
SELINUXFLAGS=-DUSE_SELINUX=1 -lselinux
endif

ifneq (,$(filter ppc64 x86_64 s390x,$(shell uname -m)))
LIBDIR 	:=	/usr/lib64
else
LIBDIR 	:=	/usr/lib
endif

all: $(EXECUTABLE) $(LIBRARY)

$(LIBRARY): selinux-mock.o
	$(LD) -shared -o $(LIBRARY) selinux-mock.o

selinux-mock.o:  selinux-mock.c
	$(CC) $(CFLAGS) -fPIC -c selinux-mock.c

$(EXECUTABLE):	$(EXECUTABLE).c
	$(CC) $(CFLAGS) $(DEBUG) -o $@ $<

clean:
	rm -f $(EXECUTABLE) $(LIBRARY)
	rm -f *~ *.bak *.o *.so

install:   $(EXECUTABLE) $(LIBRARY)
	$(INSTALL) -D -m 755 $(EXECUTABLE) $(DESTDIR)/$(SBINDIR)/$(EXECUTABLE)
	$(INSTALL) -D -m 755 $(LIBRARY) $(DESTDIR)/$(LIBDIR)/$(LIBRARY)
