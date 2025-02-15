The buildroot lockfile generator [has been modified][PR#1548] to include
additional bootstrap image metadata that can be later used for a precise image
pulling.

The mock-hermetic-repo script has also been modified, to respect the additional
metadata.  This allows us to, e.g., download bootstrap image of a different
(cross) architecture then the platform/host architecture is.  In turn, the
script is now fully arch-agnostic (any host arch may be used for downloading
files from any arch specific lockfile).
