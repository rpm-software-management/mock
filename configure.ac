#                                               -*- Autoconf -*-
# vim:tw=0:et:ts=4:sw=4
# Process this file with autoconf to produce a configure script.

####################################
# change version here. --> BOTH PLACES PLEASE!
#AC_INIT([mock],[1.2.21])

temp_RELEASE_NAME=mock
include version
####################################

#AC_PREREQ(2.61)
AC_CONFIG_AUX_DIR([build])
AM_INIT_AUTOMAKE([foreign 1.11 dist-xz no-dist-gzip])

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
for i in RELEASE_NAME RELEASE_VERSION
do
    varname=temp_$i
    if test -z "${!i}"; then
        eval $i=${!varname}; export $i
    fi
done

PACKAGE_VERSION=[`echo ${temp_VERSION}`]
VERSION=$PACKAGE_VERSION

AM_CONDITIONAL(USE_MD5, test -e /usr/bin/rpmbuild-md5)

PKG_CHECK_EXISTS([bash-completion >= 1.99],
    [BASHCOMPDIR="$($PKG_CONFIG bash-completion --variable=completionsdir|sed 's|^/usr|${prefix}|;s|^/etc|${sysconfdir}|')";HAVE_BASHCOMP2=true],
    [BASHCOMPDIR="\$(sysconfdir)/bash_completion.d"])

AC_SUBST([VERSION])
AC_SUBST([BASHCOMPDIR])
AC_SUBST([HAVE_BASHCOMP2])

# generate files and exit
AC_CONFIG_FILES([ Makefile ])
AC_OUTPUT
