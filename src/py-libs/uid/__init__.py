
import logging
log = logging.getLogger("mock.uid")

try:
    import uid
    uidManager = uid.uidManager
except ImportError, e:
    import uid_compat
    uidManager = uid_compat.uidManager
