#! /usr/bin/python3

"""
Take the JSON provided by Mock, download corresponding RPMs, and put them into
an RPM repository.
"""

import argparse
import concurrent.futures
import json
import os
import shutil
import subprocess
import sys

import requests


def download_file(url, outputdir):
    """
    Download a single file (pool worker)
    """
    file_name = os.path.join(outputdir, os.path.basename(url))
    print(f"Downloading {url}")
    try:
        with requests.get(url, stream=True, timeout=30) as response:
            if response.status_code != 200:
                return False
            with open(file_name, "wb") as fd:
                shutil.copyfileobj(response.raw, fd)
            return True
    except:
        print(f"traceback for {url}")
        raise


def _argparser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", required=True)
    parser.add_argument("--output-repo", required=True)
    return parser


def prepare_image(image_specification, outputdir):
    """
    Store the tarball into the same directory where the RPMs are
    """
    subprocess.check_output(["podman", "pull", image_specification])
    subprocess.check_output(["podman", "save", "--quiet", "-o",
                             os.path.join(outputdir, "bootstrap.tar"),
                             image_specification])


def _main():
    options = _argparser().parse_args()

    with open(options.json, "r", encoding="utf-8") as fd:
        data = json.load(fd)

    try:
        os.makedirs(options.output_repo)
    except FileExistsError:
        pass

    failed = False
    urls = [i["url"] for i in data["buildroot"]["packages"]]
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        for i, out in zip(urls, executor.map(download_file, urls,
                                             [options.output_repo for _ in urls])):
            if out is False:
                print(f"{i} download failed")
                failed = True
    if failed:
        print("Download failed")
        sys.exit(1)

    subprocess.check_call(["createrepo_c", options.output_repo])

    prepare_image(data["config"]["bootstrap_image"], options.output_repo)

if __name__ == "__main__":
    _main()
