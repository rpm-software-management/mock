The `unbreq` plugin now detects if a `BuildRequires` field is not installed on
the system and in that case does not report it as unused.

This can happen if the `BuildRequires` field is a more complex logic formula
(a case like `(foo if bar)` and `bar` is not installed on the system).

This scenario is no longer reported as warning but as info.
