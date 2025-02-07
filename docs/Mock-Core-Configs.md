---
layout: default
title: Mock Core Configs
---

# Mock core configs

Mock project provides the `mock-core-configs` package which installs the default
[configuration files](configuration) for various RPM-based Linux distributions.
This packages is typically installed with Mock by default (runtime dependency).

Other projects can provide their own configuration files in other packages, we
know of:

* [mock-centos-sig-configs](https://pagure.io/centos-sig-hyperscale/mock-centos-sig-configs)
* [RPM Fusion Mock conifgs](https://github.com/rpmfusion-infra/mock-rpmfusion)


## Maintenance

The configuration in this package maintained by the community.
When encountering an issue please use your best judgement to decide
whether a Mock config is broken, or the distribution is broken.


#### Mock config issues

If a Mock config is broken (e.g. [#756][mock-756]), please
[create a ticket for this repository][mock-issues]
and tag the responsible maintainer from the table below.


#### Distribution or repository issues

If a distribution or repository is broken (e.g. [#889][mock-889]),
please report the issue to the appropriate issue tracker for the
distribution.


#### Table

| Distribution                                                                   | Chroots           | Maintainer                                                            | Distribution or repository issue tracker |
| ------------------------------------------------------------------------------ | ----------------- | --------------------------------------------------------------------- | ------------- |
| [AlmaLinux](https://almalinux.org/)                                            | `almalinux-*`     | [@Conan-Kudo](https://github.com/Conan-Kudo), [@javihernandez](https://github.com/javihernandez) | [Issues](https://bugs.almalinux.org/)  |
| [Amazon Linux 2](https://aws.amazon.com/amazon-linux-2/)                       | `amazonlinux-2-*` | [@stewartsmith](https://github.com/stewartsmith)                      | NA  |
| [Amazon Linux](https://aws.amazon.com/linux/amazon-linux-2023/)                | `amazonlinux-*`   | [@amazonlinux](https://github.com/amazonlinux)                        | [Issues](https://github.com/amazonlinux/amazon-linux-2023/issues)  |
| [Anolis](https://openanolis.cn/)                                               | `anolis-*`        | NA                                                                    | [Issues](https://bugzilla.openanolis.cn/)  |
| [Azure Linux](https://github.com/microsoft/azurelinux)                         | `azure-linux-*`   | [@scaronni](https://github.com/scaronni)                              | [Issues](https://github.com/microsoft/azurelinux/issues)  |
| [CentOS Stream](https://www.centos.org/centos-stream/)                         | `centos-stream*`  | [Mock team][]                                                         | [Issues](https://issues.redhat.com/projects/CS)  |
| [CentOS Linux](https://www.centos.org/centos-linux/)                           | `centos*`         | End-of-life.                                                          | End-of-life.  |
| [Circle Linux](https://cclinux.org/)                                           | `circlelinux-*`   | [@bella485](https://github.com/bella485)                              | [Issues](https://bugzilla.cclinux.org/)  |
| [EuroLinux](https://en.euro-linux.com/)                                        | `eurolinux-*`     | [@nkadel](https://github.com/nkadel)                                  | [Issues](https://github.com/EuroLinux/eurolinux-distro-bugs-and-rfc)  |
| [Fedora ELN](https://docs.fedoraproject.org/en-US/eln/)                        | `fedora-eln-*`    | [@fedora-eln](https://github.com/fedora-eln)                          | [Issues](https://github.com/fedora-eln/eln/issues)  |
| [Fedora](https://fedoraproject.org/)                                           | `fedora-*`        | [Mock team][]                                                         | [Issues](https://github.com/rpm-software-management/mock/issues) |
| [Kylin](https://kylinos.cn/)                                                   | `kylin-*`         | [@scaronni](https://github.com/scaronni)                              | NA  |
| [Mageia](https://www.mageia.org/en/)                                           | `mageia-*`        | [@Conan-Kudo](https://github.com/Conan-Kudo)                          | [Issues](https://bugs.mageia.org/)  |
| [Navy Linux](https://navylinux.org/)                                           | `navy-*`          | N/A                                                                   | N/A |
| [openEuler](https://www.openeuler.org/en/)                                     | `openeuler-*`     | [@Yikun](https://github.com/Yikun)                                    | NA  |
| [OpenMandriva](https://www.openmandriva.org/)                                  | `openmandriva-*`  | [berolinux](https://github.com/berolinux)                             | [Issues](https://github.com/OpenMandrivaAssociation/distribution/issues)  |
| [openSUSE](https://www.opensuse.org/)                                          | `opensuse-*`      | [@Conan-Kudo](https://github.com/Conan-Kudo), [@lkocman](https://github.com/lkocman) | [Issues](https://bugzilla.opensuse.org/)  |
| [Oracle Linux](https://www.oracle.com/linux/)                                  | `oraclelinux-*`   | [@Mno-hime](https://github.com/Mno-hime)                              | [issues](https://github.com/oracle/oracle-linux/issues) |
| [RHEL](https://www.redhat.com/en/technologies/linux-platforms/enterprise-linux)| `rhel-*`          | [Mock team][]                                                         | [Issues](https://issues.redhat.com/projects/RHEL)  |
| [Rocky Linux](https://rockylinux.org/)                                         | `rocky-*`         | [@nazunalika](https://github.com/nazunalika)                          | [Issues](https://bugs.rockylinux.org/)  |


[Mock team]: https://github.com/orgs/rpm-software-management/teams/mock-team
[mock-issues]: https://github.com/rpm-software-management/mock/issues
[mock-756]: https://github.com/rpm-software-management/mock/issues/756
[mock-889]: https://github.com/rpm-software-management/mock/issues/889
