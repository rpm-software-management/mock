These 3 src.rpms are setup to build on almost any rpm-based system.
They have a simple chain of buildrequires:

test-A BuildRequires test-B
test-B BuildRequires test-C

So using a normal shell expansion the packages built like:

mock --chain -r fedora-18-x86_64 *.src.rpm

will fail to build b/c test-A will be built first and it won't have
its buildreqs satisified.

Tests to run:

test failure:
mock --chain -r fedora-18-x86_64 *.src.rpm

test partial failure:
mock --chain -r fedora-18-x86_64 -c *.src.rpm

test complete success:
mock --chain -r fedora-18-x86_64 -c test-C-1.1-0.src.rpm test-B-1.1-0.src.rpm test-A-1.1-0.src.rpm

test success due to recursive rebuild:
mock --chain -r fedora-18-x86_64 --recurse *.src.rpm

