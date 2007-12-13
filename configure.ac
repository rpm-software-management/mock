#                                               -*- Autoconf -*-
# vim:tw=0:et:ts=4:sw=4
# Process this file with autoconf to produce a configure script.

####################################
# change version here.
AC_INIT([mock],[0.8.18])

temp_RELEASE_NAME=mock
temp_RELEASE_MAJOR=0
temp_RELEASE_MINOR=8
temp_RELEASE_SUBLEVEL=18
temp_RELEASE_EXTRALEVEL=

####################################

AC_PREREQ(2.61)
AC_CONFIG_AUX_DIR([build])
AM_INIT_AUTOMAKE
AM_MAINTAINER_MODE

# Checks for programs.
AC_PROG_CC
AC_PROG_CPP
AC_PROG_LIBTOOL
AC_PROG_INSTALL

# automake macros
AM_PROG_CC_C_O
AM_PATH_PYTHON

# Checks for header files.
AC_HEADER_STDC
AC_HEADER_SYS_WAIT
AC_CHECK_HEADERS([stdlib.h string.h unistd.h])
AC_CONFIG_HEADERS([src/config.h])

# Checks for typedefs, structures, and compiler characteristics.
AC_C_CONST
AC_TYPE_PID_T

# Checks for library functions.
AC_FUNC_ALLOCA
AC_FUNC_ERROR_AT_LINE
AC_CHECK_FUNCS([strerror])

# update 'real' variables from the temp variable names.
# do this at the end of the file so that they A) are not overwitten by other
# autoconf stuff, and B) so that user can override on cmdline
for i in RELEASE_NAME RELEASE_MAJOR RELEASE_MINOR RELEASE_SUBLEVEL RELEASE_EXTRALEVEL
do
    varname=temp_$i
    if test -z "${!i}"; then
        eval $i=${!varname}; export $i
    fi
done

# Update the version information only immediately before a public release of your software. More frequent updates are unnecessary, and only guarantee that the current interface number gets larger faster.
# If the library source code has changed at all since the last update, then increment revision (c:r:a becomes c:r+1:a).
# If any interfaces have been added, removed, or changed since the last update, increment current, and set revision to 0.
# If any interfaces have been added since the last public release, then increment age.
# If any interfaces have been removed since the last public release, then set age to 0. 
MOCK_LIBTOOL_CURRENT=$(( $RELEASE_MAJOR + 1 ))
MOCK_LIBTOOL_REVISION=$RELEASE_MINOR
MOCK_LIBTOOL_AGE=0

if test -z "$RELEASE_RPM_EXTRALEVEL"; then
    if test -z "$RELEASE_EXTRALEVEL"; then
        RELEASE_RPM_EXTRALEVEL=%{nil}
    else
        RELEASE_RPM_EXTRALEVEL=$RELEASE_EXTRALEVEL
    fi
fi

PACKAGE_VERSION=[`echo ${RELEASE_MAJOR}.${RELEASE_MINOR}.${RELEASE_SUBLEVEL}${RELEASE_EXTRALEVEL}`]
PACKAGE_STRING=[`echo ${RELEASE_NAME} ${RELEASE_MAJOR}.${RELEASE_MINOR}.${RELEASE_SUBLEVEL}${RELEASE_EXTRALEVEL}`]
VERSION=$PACKAGE_VERSION

cat confdefs.h |
    grep -v 'define VERSION ' |
    grep -v 'define PACKAGE_VERSION ' |
    grep -v 'define PACKAGE_STRING '  > confdefs.new
mv confdefs.new confdefs.h
cat >>confdefs.h <<_ACEOF 
#define VERSION "$VERSION"
#define PACKAGE_VERSION "$PACKAGE_VERSION"
#define PACKAGE_STRING "$PACKAGE_STRING"
_ACEOF

AC_SUBST([RELEASE_NAME RELEASE_MAJOR RELEASE_MINOR RELEASE_SUBLEVEL RELEASE_EXTRALEVEL RELEASE_RPM_EXTRALEVEL])
AC_SUBST([ MOCK_LIBTOOL_CURRENT  MOCK_LIBTOOL_REVISION MOCK_LIBTOOL_AGE  ])

# check if build dir == source dir.
AM_CONDITIONAL([BLD_SRC_DIFFERENT], [test x$srcdir != x.])

# generate files and exit
AC_CONFIG_FILES([ Makefile src/version.h mock.spec ])
AC_OUTPUT

