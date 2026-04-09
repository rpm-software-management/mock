Set bootstrap_image_ready=True for AlmaLinux configs.  AlmaLinux container
images now have python3-dnf-plugins-core available by default, so Mock skips
updating the bootstrap chroot after extracting the image.
