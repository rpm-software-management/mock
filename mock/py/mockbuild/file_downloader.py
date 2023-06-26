# -*- coding: utf-8 -*-
# vim: noai:ts=4:sw=4:expandtab

from email.message import Message
import shutil
import tempfile
from urllib.parse import urlsplit

import backoff
import requests

from .trace_decorator import getLog


def _filename_from_response(response):
    if 'content-disposition' in response.headers:
        # https://peps.python.org/pep-0594/#cgi
        parser = Message()
        parser["content-type"] = response.headers['content-disposition']
        if parser.get_param("filename"):
            return parser.get_param("filename")
    return urlsplit(response.url).path.rsplit('/', 1)[1]


class FileDownloader:
    """
    Download files into a temporary storage with automatic cleanup with
    cls.cleanup(), remembering both original URL and the local path name.
    """

    tmpdir = None

    @classmethod
    def _initialize(cls):
        if cls.tmpdir:
            return
        cls.backmap = {}
        cls.tmpdir = tempfile.mkdtemp()

    @classmethod
    def get(cls, pkg_url_or_local_file):
        """
        If the pkg_url_or_local_file looks like a link, try to download it and
        store it to a temporary directory - and return path to the local
        downloaded file.

        If the pkg_url_or_local_file is not a link, do nothing - just return
        the pkg_url_or_local_file argument.
        """
        pkg = pkg_url_or_local_file
        log = getLog()

        url_prefixes = ['http://', 'https://', 'ftp://']
        if not any(pkg.startswith(pfx) for pfx in url_prefixes):
            log.debug("Local file: %s", pkg)
            return pkg

        cls._initialize()
        try:
            log.info('Fetching remote file %s', pkg)
            return cls._get_inner(pkg)
        except requests.exceptions.RequestException as e:
            log.error('Downloading error %s: %s', pkg, str(e))
            return None

    @classmethod
    @backoff.on_exception(backoff.expo, requests.exceptions.RequestException,
                          max_tries=3, max_time=100)
    def _get_inner(cls, url):
        req = requests.get(url, timeout=30)
        req.raise_for_status()
        filename = _filename_from_response(req)
        pkg = cls.tmpdir + '/' + filename
        with open(pkg, 'wb') as filed:
            for chunk in req.iter_content(4096):
                filed.write(chunk)
        cls.backmap[pkg] = url
        return pkg

    @classmethod
    def original_name(cls, localname):
        """ Get the URL from the local name """
        if not cls.backmap:
            return localname
        return cls.backmap.get(localname, localname)

    @classmethod
    def cleanup(cls):
        """ Remove the temporary storage with downloaded RPMs """
        if not cls.tmpdir:
            return
        getLog().debug("Cleaning the temporary download directory: %s", cls.tmpdir)
        cls.backmap = {}
        # cleaning up our download dir
        shutil.rmtree(cls.tmpdir, ignore_errors=True)
        cls.tmpdir = None
