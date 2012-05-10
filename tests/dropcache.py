#!/usr/bin/python

import os
import sys

if os.getuid() != 0:
    print "must be root to drop caches!"
    sys.exit(-1)

print "******************* dropping caches"
open('/proc/sys/vm/drop_caches', 'w').write("3")
sys.exit(0)
