#! /bin/python3

import os
from glob import glob
import sys
import subprocess


def _do_scrub(configs, weird, chroot, suffix=None):
    if suffix and chroot + "-" + suffix in weird:
        print(f"skipping weird scrub: {chroot} {suffix}")
        return

    base_cmd = ["mock", "--scrub=all", "-r"]
    cmd = base_cmd + ["eol/" + chroot if configs[chroot] == "eol" else chroot]
    if suffix is not None:
        cmd += ["--uniqueext", suffix]
    subprocess.call(cmd)


def _main():
    configs = {}
    scrub = set()
    scrub_bootstrap = set()
    scrub_uniqueext = set()
    scrub_uniqueext_bootstrap = set()
    scrub_weird = set()
    guessing_suffix = {}

    for item in glob("/etc/mock/*.cfg"):
        configs[os.path.basename(item)[:-4]] = "normal"
    for item in glob("/etc/mock/eol/*.cfg"):
        configs[os.path.basename(item)[:-4]] = "eol"

    for directory in glob("/var/lib/mock/*") + glob("/var/cache/mock/*"):
        if not os.path.isdir(directory):
            continue

        directory = os.path.basename(directory)

        if directory in configs:
            scrub.add(directory)
            continue

        if directory.endswith("-bootstrap"):
            directory_no_bootstrap = directory[:-10]
            if directory_no_bootstrap in configs:
                scrub_bootstrap.add(directory_no_bootstrap)
                continue

        guessing_suffix[directory] = None

    for config, config_type  in configs.items():
        for directory in list(guessing_suffix.keys()):
            if guessing_suffix[directory]:
                # already found the cleaning thing
                continue

            if directory.startswith(config):

                suffix = directory[len(config)+1:]
                if suffix.endswith("-bootstrap"):
                    # See this:
                    # 1. alma+epel-8-x86_64-php-bootstrap
                    # 2. alma+epel-8-x86_64-bootstrap-php
                    # The 1. is weird, and we miss the corresponding
                    # configuration.  The second could be a "php" uniqueext.
                    weird_chroot = directory[:-10]
                    scrub_weird.add(weird_chroot)
                    continue

                start = "bootstrap-"
                if suffix.startswith(start):
                    suffix = suffix[len(start):]
                    scrub_uniqueext_bootstrap.add((config, suffix))
                else:
                    scrub_uniqueext.add((config, suffix))

                guessing_suffix[directory] = "uniqueext"



    for sc, suffix in scrub_uniqueext_bootstrap - scrub_uniqueext:
        _do_scrub(configs, scrub_weird, sc, suffix)


    for sc, suffix in scrub_uniqueext:
        _do_scrub(configs, scrub_weird, sc, suffix)

    for only_bootstrap in scrub_bootstrap - scrub:
        _do_scrub(configs, scrub_weird, only_bootstrap)

    for sc in scrub:
        _do_scrub(configs, scrub_weird, sc)

    for directory, found in guessing_suffix.items():
        if found:
            continue
        print(f"Unknown directory: {directory}")


if __name__ == "__main__":
    sys.exit(_main())
