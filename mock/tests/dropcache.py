#!/usr/bin/python3

import os
import sys

if os.getuid() != 0:
    print("must be root to drop caches!")
    sys.exit(-1)

print("******************* dropping caches")
with open('/proc/sys/vm/drop_caches', 'w') as f:
    f.write("3")
sys.exit(0)
