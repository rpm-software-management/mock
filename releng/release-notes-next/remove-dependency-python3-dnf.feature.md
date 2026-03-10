Previously we used python3-dnf to detect system architecture to guess default mock's config.
As python3-dnf is going to be removed and python3-libdnf5 does not have this function we
call directly rpm command to retrive the correct string.
