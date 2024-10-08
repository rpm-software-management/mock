"""
Global configuration for Mock's behave tests
"""

import os
import pwd
import random
import shutil
import string
import tempfile

import requests

from testlib.mock import Mock
from testlib.commands import no_output


def _random_string(length):
    return ''.join(random.choices(string.ascii_lowercase + string.digits,
                                  k=length))


def _download(context, url):
    print(f'Downloading {url}')
    req = requests.get(url, timeout=60)
    filename = os.path.join(context.workdir, os.path.basename(url))
    with open(filename, 'wb') as dfd:
        dfd.write(req.content)
    return filename


def _download_rpm(context, rpm):
    files = {
        "always-installable":
            "repo/always-installable-1-0.fc32.noarch.rpm",
        "buildrequires-always-installable":
            "buildrequires-always-installable-1-0.src.rpm",
    }
    return _download(context, "/".join([context.test_storage, files[rpm]]))


def before_all(context):
    """ executed before all the testing starts, only once per behave run """
    context.uniqueext = _random_string(8)
    context.uniqueext_used = False

    # detect the default used chroot from default.cfg link
    default_config = os.readlink("/etc/mock/default.cfg")
    context.chroot = default_config[:-4]  # drop cfg suffix

    context.test_storage = (
        "https://github.com/"
        "rpm-software-management/mock-test-data/raw/main/")

    context.download = lambda url: _download(context, url)
    context.download_rpm = lambda rpm: _download_rpm(context, rpm)
    context.next_mock_options = []


def _cleanup_workdir(context):
    shutil.rmtree(context.workdir)
    context.workdir = None
    context.custom_config = ""


def before_scenario(context, _scenario):
    """ execute before - once for each - scenario """
    context.workdir = tempfile.mkdtemp(prefix="mock-behave-tests-")
    context.custom_config = ""
    context.add_cleanup(_cleanup_workdir, context)
    context.mock = Mock(context)
    context.add_repos = []
    context.current_user = pwd.getpwuid(os.getuid())[0]


def after_scenario(context, _scenario):
    """ execute after - and for each - scenario """
    with no_output():
        context.mock.clean()
