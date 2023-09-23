The fixes introduced in Mock 5.1 included a compatibility issue with Python in
Enterprise Linux 8 due to a dependency on the `capture_output=True` feature in
the `subprocess` module, which was added in Python 3.7.  However, EL 8 is
running on Python 3.6.  This compatibility issue has been resolved in Mock by
using `stdout=subprocess.PIPE` instead.  This update was made based on a [report
from Bodhi update](https://bodhi.fedoraproject.org/updates/FEDORA-EPEL-2023-45ace77fca).
