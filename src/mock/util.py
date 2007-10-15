
import rpmUtils
import rpmUtils.transaction
import sys

# needs porting...
def ensure_filetype_srpm(srpms):
    for srpm in srpms:
        ts = rpmUtils.transaction.initReadOnlyTransaction()
        try:
            hdr = rpmUtils.miscutils.hdrFromPackage(ts, srpm)
        except rpmUtils.RpmUtilsError, e:
            error("Specified srpm %s cannot be found/opened" % srpm)
            sys.exit(50)
   
        if hdr[rpm.RPMTAG_SOURCEPACKAGE] != 1:
            error("Specified srpm isn't a srpm!  Can't go on")
            sys.exit(50)


