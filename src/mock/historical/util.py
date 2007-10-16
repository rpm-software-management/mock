
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


def _umount(self, path):
    if path.find(self.rootdir) == -1:
        item = '%s/%s' % (self.rootdir, path)
    else:
        item = path
    command = '%s %s' % (self.config['umount'], item)
    (retval, output) = self.do(command)

    if retval != 0:
        if output.find('not mounted') == -1: # this probably won't work in other LOCALES
            error(output)
            raise RootError, "could not umount %s error was: %s" % (path, output)
            
def _text_requires_from_hdr(self, hdr, srpm):
    """take a header and hand back a unique'd list of the requires as
       strings"""
   
    reqlist = []
    names = hdr[rpm.RPMTAG_REQUIRENAME]
    flags = hdr[rpm.RPMTAG_REQUIREFLAGS]
    ver = hdr[rpm.RPMTAG_REQUIREVERSION]
    if names is not None:
        tmplst = zip(names, flags, ver)
    
    for (n, f, v) in tmplst:
        if n.startswith('rpmlib'):
            continue

        req = rpmUtils.miscutils.formatRequire(n, v, f)
        reqlist.append(req)
    
    # Extract SRPM name components - still not nice, shouldn't this
    # be somewhere in the "hdr" parameter?
    fname = os.path.split(str(srpm))[1]
    name, ver, rel, epoch, arch = rpmUtils.miscutils.splitFilename(fname)

    # Add the 'more_buildreqs' for this SRPM (if defined)
    for this_srpm in ['-'.join([name,ver,rel]),
                      '-'.join([name,ver]),
                      '-'.join([name]),]:
        if self.config['more_buildreqs'].has_key(this_srpm):
            more_reqs = self.config['more_buildreqs'][this_srpm]
            if type(more_reqs) in (type(u''), type(''),):
                more_reqs = [more_reqs] # be nice if we get a string
            for req in more_reqs:
                reqlist.append(req)
            break
    
    return rpmUtils.miscutils.unique(reqlist)


def do_chroot(self, command, fatal = False, exitcode=None, timeout=0):
    """execute given command in root"""
    cmd = ""
    
    if command.find('-c "') > -1:
        cmd = "%s %s %s" % (self.config['chroot'], self.rootdir, command)
    else:
        # we use double quotes to protect the commandline since
        # we use single quotes to protect the args in command
        # weird - why is it finding this at all.
        cmd = "%s %s %s - root -c \"%s\"" % (self.config['chroot'],
                                             self.rootdir,
                                             self.config['runuser'],
                                             command)
    (ret, output) = self.do(cmd, timeout=timeout)
    if (ret != 0) and fatal:
        self.close()
        if exitcode:
            ret = exitcode
        error("Non-zero return value %d on executing %s\n" % (ret, cmd))
        error(output)
        sys.exit(ret)
    return (ret, output)


def do(self, command, timeout=0):
    """execute given command outside of chroot"""
    class alarmExc(Exception): pass
    def alarmhandler(signum,stackframe):
        raise alarmExc("timeout expired")
    
    retval = 0
    msg = "Executing timeout(%s): %s" % (timeout, command)
    self.debug(msg)
    self.root_log(msg)

    if hasattr(self, '_root_log'):
        logfile = self._root_log
    else:
        logfile = self.tmplog
    if self.state() == "build":
        logfile = self._build_log

    output=""
    (r,w) = os.pipe()
    pid = os.fork()
    if pid: #parent
        rpid = ret = 0
        os.close(w)
        oldhandler=signal.signal(signal.SIGALRM,alarmhandler)
        starttime = time.time()
        # timeout=0 means disable alarm signal. no timeout
        signal.alarm(timeout)

        try:
            # read output from child
            r = os.fdopen(r, "r")
            for line in r:
                logfile.write(line)
                if self.config['debug'] or self.config['verbose']:
                    print line[:-1]
                    sys.stdout.flush()
                logfile.flush()
                output += line

            # close read handle, get child return status, etc
            r.close()
            (rpid, ret) = os.waitpid(pid, 0)
            signal.alarm(0)
            signal.signal(signal.SIGALRM,oldhandler)

        except alarmExc:
            os.kill(-pid, signal.SIGTERM)
            time.sleep(1)
            os.kill(-pid, signal.SIGKILL)
            (rpid, ret) = os.waitpid(pid, 0)
            signal.signal(signal.SIGALRM,oldhandler)
            raise commandTimeoutExpired( "Timeout(%s) exceeded for command: %s" % (timeout, command))

        # mask and return just return value, plus child output
        return ((ret & 0xFF00) >> 8, output)

    else: #child
        os.close(r)
        # become process group leader so that our parent
        # can kill our children
        os.setpgrp()  

        child = popen2.Popen4(command)
        child.tochild.close()

        w = os.fdopen(w, "w")
        for line in child.fromchild:
            w.write(line)
        w.close()
        retval=child.wait()
        os._exit( (retval & 0xFF00) >> 8 )


