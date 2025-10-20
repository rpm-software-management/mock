The suppress-sync option that was introduced in the previous release caused
regression in some packages that use `sync()` during `%check`. Because of that,
it was disabled by default, and you can enable it as opt-in.
[#1641](https://github.com/rpm-software-management/mock/issues/1641)
