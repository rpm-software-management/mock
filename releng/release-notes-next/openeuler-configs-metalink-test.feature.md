Add a `%check` test to mock-core-configs that asserts openEuler source
repositories use the literal `openEuler-<version>` directory in
`metalink ... path=` URLs rather than the untranslated `$releasever`,
which the metalink `path=` form does not expand.
