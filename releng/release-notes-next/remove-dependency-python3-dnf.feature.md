Previously we used python3-dnf to detect system architecture to guess default mock's config.
As python3-dnf is going to be removed we now try to use function from python3-libdnf5. And if it fails we
try to use the old function from python3-dnf.
This should preserve functionality on both modern and old systems.
