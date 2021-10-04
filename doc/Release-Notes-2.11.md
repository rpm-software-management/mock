---
layout: default
title: Release Notes 2.11
---

Released on - 2021-06-09


## Mock 2.11 features:

 * You can use `--cwd` together with `--shell` now. [[PR 732][PR#732]]

 * You can use `mock --install 'external:pypi:hwdata'` now. [[PR 733][PR#733]]

 * Mock now defines macro `%{_platform_multiplier}` which is set to 1 by default. However, when [forcearch][forcearch] is used, then it is set to 10. [[PR 730][PR#730]]

   This can be used to tune timeouts in e.g., `%check` and reflects that emulated platforms can take longer to finish task. Suggested use case can be:

    ```
    %{!?_platform_multiplier:%global _platform_multiplier 1}
    timeout $(( 60*%_platform_multiplier )) the-long-running-task
    ```

   This will timeout after 60 seconds but on emulated platforms after 600 seconds.

   If you have slow builder for some architecture, you can put in your config

   ```
   config_opts['macros']['%_platform_multiplier'] = 5
   ```

   to tune up this macro.

## Mock 2.11 bugfixes:

 * Plug-in `compress_logs` now compresses log files even in case of DNF
   repository failures [[PR 736][PR#736]].

 * Broken "usage" section in `mock --help` output was fixed [[issue 738][#738]].


## Mock-core-configs v34.4:

 * centos-stream-8 repositories use mirrorlist now. And have additional repositories which are presented in default centos-stream-8 installation [[PR 729][PR#729]]

The following contributors contributed to this release:

 * Neal Gompa
 * Miroslav Suchý

Thank you!

[PR#729]: https://github.com/rpm-software-management/mock/pull/729
[PR#730]: https://github.com/rpm-software-management/mock/pull/730
[PR#732]: https://github.com/rpm-software-management/mock/pull/732
[PR#733]: https://github.com/rpm-software-management/mock/pull/733
[PR#736]: https://github.com/rpm-software-management/mock/pull/736
[#738]: https://github.com/rpm-software-management/mock/issues/738
[forcearch]: https://github.com/rpm-software-management/mock/wiki/Feature-forcearch
