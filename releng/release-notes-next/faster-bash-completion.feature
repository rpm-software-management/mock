The Bash completion script for Mock has been improved to pre-compile the list of
available Mock options at package build-time.  This enhancement significantly
reduces the time required for option completion from approximately 0.5 seconds
(on a reasonably fast laptop) to just 0.05 seconds. [rhbz#2259430][].
