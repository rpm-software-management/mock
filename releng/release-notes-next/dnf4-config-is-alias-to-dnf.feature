Alias `dnf4` added for the `package_manager = dnf`.

The options specific to DNF4, previously prefixed with `dnf_*`, have been
renamed to `dnf4_*` too to avoid confusion with `dnf5_*` options.  For backward
compatibility, the `dnf_*` prefixed variants still work, so these config pairs
are equivalent:

```python
config_opts['dnf4_install_cmd'] = 'install python3-dnf python3-dnf-plugins-core'
config_opts['dnf_install_cmd'] = 'install python3-dnf python3-dnf-plugins-core'

config_opts['package_manager'] = 'dnf4'
config_opts['package_manager'] = 'dnf'
```

Some of the `dnf_*` options remain unchanged because they are universal and used
with DNF4, DNF5, or YUM, e.g., `dnf_vars`.

While working on this rename, the rarely used `system_<PM>_command` options have
been changed to `<PM>_system_command` to visually align with the rest of the
package-manager-specific options. The old variants are still accepted.
