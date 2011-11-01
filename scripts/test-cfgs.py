#!/usr/bin/python -tt
#
# Script to check validity of mock config URLs
#

import os
import os.path
import sys
import glob
import urllib2

class Config(object):
    def __init__(self, file):
        self.path = file
        self.cfg = os.path.basename(self.path)[0:-4]
        self.stanzas = []
        self.map = {}
        current_key = ''
        for l in open(self.path):
            l = l.strip()
            if l.startswith('#'): continue
            if l.startswith('['):
                key = l[1:l.rindex(']')]
                current_key = key
                if key == 'main' or key == 'local': continue
                self.stanzas.append(current_key)
                self.map[current_key] = {}
                continue
            if 'http://' in l:
                if current_key == 'main' or current_key == 'local': continue
                i = l.index('=')
                key = l[0:i]
                url = l[i+1:]
                self.map[current_key][key.strip()] = url.strip()
                continue

    def __str__(self):
        return self.cfg

    def check_urls(self):
        print self.cfg
        total_sites = 0;
        for s in self.stanzas:
            for k in self.map[s].keys():
                if k == 'mirrorlist':
                    num = self.check_mirrorlist(self.map[s][k])
                    if num == 0:
                        print "\t[%s] Error: no mirror sites\t<-------" % s
                    else:
                        print "\t[%s] Ok (%d sites)" % (s, num)
                    total_sites += num
                elif k == 'baseurl':
                    if self.check_baseurl(self.map[s][k]) == 0:
                        print "\t[%s] Error: no files for baseurl\t<-------" % s
                    else:
                        print "\t[%s] baseurl Ok" %s
                        total_sites += 1
                else:
                    raise RuntimeError, "Unknown URL type in %s: %s" % (s, k)
        if total_sites == 0:
            print "    %s has no valid URLs" % self.cfg

    def check_mirrorlist(self, url):
        #print "checking mirrorlist at %s" % url
        try:
            lines = [ l for l in urllib2.urlopen(url).readlines() if not l.startswith('#') and len(l.strip()) != 0 ]
            if len(lines) == 1 and lines[0].startswith('Bad arch'):
                return 0
            return len(lines)
        except urllib2.URLError, e:
            pass
        return 0

    def check_baseurl(self, url):
        #print "checking baseurl at %s" % url
        try:
            data = urllib2.urlopen(url).readlines()
        except urllib2.HTTPError, e:
            return 0
        except urllib2.URLError, e:
            return 0
        return len(data)

if __name__ == '__main__':
    configs = glob.glob('etc/mock/*.cfg')
    configs.sort()
    for c in configs:
        if os.path.basename(c).startswith('site-defaults'): continue
        Config(c).check_urls()

