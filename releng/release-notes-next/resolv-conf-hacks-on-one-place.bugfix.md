The NS resolver munging was previously scattered across multiple locations in
the Mock codebase.  This duplication made the logic difficult to follow and led
to bugs, such as the one addressed in [PR#1697][].  This change simplifies and
consolidates the code.
