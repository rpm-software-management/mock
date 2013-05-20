#!/usr/bin/python -tt
# skvidal at fedoraproject.org

# take a set of srpms
# resolve their buildreqs (pkg name only  - not version or virtual build provide)
# sort them
# break them into groups for parallelizing the build
# this uses the topsort from:
# https://pypi.python.org/pypi/topsort/0.9
# which uses rad_util from:
# https://pypi.python.org/pypi/rad_util/0.45

import sys
import tempfile
import rpm
import subprocess
import os
import glob
import yum
import topsort

def return_binary_pkgs_from_srpm(srpmfn):
    mydir = tempfile.mkdtemp()
    binary_pkgs = []
    rc = subprocess.Popen(['rpm2cpio', srpmfn],stdout=subprocess.PIPE)
    cs = subprocess.Popen(['cpio', '--quiet', '-i', '*.spec'], cwd=mydir,
                          stdin=rc.stdout, stdout=subprocess.PIPE, stderr=open('/dev/null', 'w'))
    output = cs.communicate()[0]
    specs = glob.glob(mydir + '/*.spec')
    if not specs:
        return binary_pkgs
    spkg = rpm.spec(specs[0])
    for p in spkg.packages:
        binary_pkgs.append(p.header['name'])
    return binary_pkgs



def get_buildreqs(srpms):
    my = yum.YumBase()
    my.preconf.init_plugins=False
    my.setCacheDir()
    build_reqs = {}
    build_bin = {}
    srpms_to_pkgs = {}

    for i in srpms:
        # generate the list of binpkgs the srpms create 
        srpm_short = os.path.basename(i)
        build_bin[srpm_short] = return_binary_pkgs_from_srpm(i)

        # generate the list of provides in the repos we know about from those binpkgs (if any)
        p_names = []
        for name in build_bin[srpm_short]:
            providers = my.pkgSack.searchNevra(name=name)
            if providers:
                p_names.extend(providers[0].provides_names)
        build_bin[srpm_short].extend(p_names)

    for i in srpms:
        # go through each srpm and take its buildrequires and resolve them out to one of other
        # srpms, if possible using the build_bin list we just generated
        # toss out any pkg which doesn't map back - this only does requires NAMES - not versions
        # so don't go getting picky about versioning here.
        lp = yum.packages.YumLocalPackage(filename=i)
        srpm_short = os.path.basename(i)
        # setup the build_reqs
        build_reqs[srpm_short] = set([])
        srpms_to_pkgs[srpm_short] = lp
        for r in lp.requires_names:
            for srpm in build_bin:
                if r in build_bin[srpm]:
                    build_reqs[srpm_short].add(srpm)

    return build_reqs
    
def main():
    if len(sys.argv) < 2:
        print 'usage: buildorder.py srpm1 srpm2 srpm3'
        sys.exit(1)
    
    srpms = sys.argv[1:]
    print 'Sorting %s srpms' % len(srpms)

    print 'Getting build reqs'
    build_reqs = get_buildreqs(srpms)
    
    print 'Breaking loops, brutally'
    # need to break any loops up before we pass it to the tsort
    # we warn and nuke the loop - tough noogies - you shouldn't have them anyway
    broken_loop_unsorted = {}
    for (node,reqs) in build_reqs.items():
        broken_loop_unsorted[node] = []
        for p in reqs:
            if node in build_reqs[p]:
                print 'WARNING: loop: %s and %s' % (node, p)
            else:
                broken_loop_unsorted[node].append(p)

    build_reqs = broken_loop_unsorted

    # make the pairslist that topsort() wants
    pairs = []
    for (k, reqs) in build_reqs.items():
        pairs.append((k,'None'))
        for r in reqs:
            pairs.append((k,r))

    return_count = 0
    print 'Full sorted list - in build order:'
    for i in reversed(topsort.topsort(pairs)):
        if i != 'None':
            print i
            return_count += 1
    

    print 'NOTE: broken out into groups of pkgs that can be built'
    print 'NOTE: each group must be built before the next set can be built'
    print 'NOTE: all pkgs within each group can be built in parallel'
    
    print 'groups:'

    levels = [ level for level in topsort.topsort_levels(pairs) ]
    # in order to preserve the leaf nodes we have to have them dependent on None
    # prune None out of the levels we get back
    
    for l in levels[:]:
        if 'None' in l:
            l.remove('None')
        if not l:
            levels.remove(l)
        
        
    group_num = 1
    for l in reversed(levels):
        print 'group: %s' % group_num
        for i in l:
            if i != 'None':
                print '  ' + i
        group_num += 1


    if return_count != len(srpms):
        print 'NOTE: returned packages does not match number of srpms in input, could be an error'
        print 'NOTE: %s srpms vs %s returned packages' % (len(srpms), return_count)

    

if __name__ == '__main__':
    main()


