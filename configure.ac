#                                               -*- Autoconf -*-
# vim:tw=0:et:ts=4:sw=4
# Process this file with autoconf to produce a configure script.

####################################
# change version here. --> BOTH PLACES PLEASE!
AC_INIT([mock],[0.9.10])

temp_RELEASE_NAME=mock
temp_RELEASE_MAJOR=0
temp_RELEASE_MINOR=9
temp_RELEASE_SUBLEVEL=10
temp_RELEASE_EXTRALEVEL=
####################################

AC_PREREQ(2.61)
AC_CONFIG_AUX_DIR([build])
AM_INIT_AUTOMAKE
AM_MAINTAINER_MODE

# Checks for programs.
AC_PROG_INSTALL

# automake macros
AM_PATH_PYTHON

# Checks for header files.

# Checks for typedefs, structures, and compiler characteristics.

# Checks for library functions.

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

AC_SUBST([RELEASE_NAME RELEASE_MAJOR RELEASE_MINOR RELEASE_SUBLEVEL RELEASE_EXTRALEVEL RELEASE_RPM_EXTRALEVEL])

# generate files and exit
AC_CONFIG_FILES([ Makefile ${PACKAGE_NAME}.spec ])
AC_OUTPUT

