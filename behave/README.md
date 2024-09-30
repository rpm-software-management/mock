BDD for Mock
============

This test-suite can destroy your system!  Not intentionally, but some steps
require us to use root (e.g. install or remove packages).  **Never** execute
this test suite on your host system, allocate some disposable machine.

How to run the tests
--------------------

1. Install the Mock RPM that you want to test.

2. Run `$ behave` command in this directory, with `--tags tagname` if you want
   to test only subset of all provided scenarios.
