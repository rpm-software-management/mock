A new `{{ repo_arch }}` Jinja2 template (templated-dictionary) is provided
by Mock.  This variable is usable for DNF config options denoting URLs like
`baseurl=`, `metalink=`, etc.  Namely, it can be used instead of the DNF-native
`$basearch` variable which [doesn't work properly for all the
distributions][issue#1304].  The new `config_opts['repo_arch_map']` option has
been added too, if additional tweaks with `repo_arch` template need to be done.
