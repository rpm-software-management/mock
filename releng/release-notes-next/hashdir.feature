A new option `hashdir` has been [added][PR#1399] to the ccache plugin. Setting
it to false the build working directory from the hash used to distinguish two
compilations when generating debuginfo. While this allows the compiler cache
to be shared across different package NEVRs, it might cause the debuginfo to be
incorrect.
The option can be used for issue bisecting if running the debugger is
unnecessary. ([issue#1395][])
