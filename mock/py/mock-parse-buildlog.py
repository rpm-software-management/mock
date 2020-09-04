#!/usr/bin/python3 -tt
# -*- coding: utf-8 -*-
# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# pylint: disable=invalid-name

import argparse
import logging
import re

FORMAT = "%(levelname)s: %(message)s"
logging.basicConfig(format=FORMAT, level=logging.WARNING)
log = logging.getLogger()


def argumentParser():
    parser = argparse.ArgumentParser(
        description="Parses the build.log and return an error why build failed.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("-p", "--path", required=True, help="Path to build.log")
    arguments = parser.parse_args()
    return arguments


def parseBuildLog(log_path):
    """Parses the build log.

    Args:
        log_path (str): Path to the RPM build log.

    Returns:
        tuple: The first element is the type of error that was found
            in the log (missing or deleted). The second element is
            a list of problematic files.
    """
    try:
        with open(log_path, "r") as build_log:
            lines = build_log.read().splitlines()
    except IOError as error:
        log.error("There was an error opening %s, %s", log_path, str(error))
        return

    error_re = re.compile(
        r"""
        ^
        (BUILDSTDERR:)?
        \s*
        (
            (?P<missing>File\s+not\s+found:\s*)|
            (?P<unpackaged>Installed\s+\(but\s+unpackaged\)\s+file\(s\)\s+found:)
        )?
        (?P<path>/.*)?
        $
        """, re.VERBOSE,
    )

    error_type = None
    files = set()

    for line in lines:
        match = error_re.match(line)
        if match:
            if match.group("missing"):
                error_type = "deleted"
                files.add(match.group("path"))
            elif match.group("unpackaged"):
                error_type = "missing"
            elif error_type == "missing" and match.group("path"):
                files.add(match.group("path"))
            elif error_type and not match.group("path"):
                break

    return error_type, list(files)


def main(log_path):
    error = parseBuildLog(log_path)
    if error[0] is not None:
        if error[0] == "missing":
            print(
                "Error type: {0}".format("Build failed because problematic files are in %buildroot but not in %files")
            )
        elif error[0] == "deleted":
            print(
                "Error type: {0}".format("Build failed because problematic files are in %files but not in %buildroot")
            )
        print("Problematic files: ")
        for files in error[1]:
            print(files)
    else:
        log.error("Couldn't recognize the error that caused the build failure.")


if __name__ == "__main__":
    programArguments = argumentParser()
    main(programArguments.path)
