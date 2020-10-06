# -*- coding: utf-8 -*-
# vim: noai:ts=4:sw=4:expandtab

import cgi
import shutil
import tempfile
from urllib.parse import urlsplit

import requests

from .trace_decorator import getLog


class FileDownloader:
    tmpdir = None
    backmap = None

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
        if not any([pkg.startswith(pfx) for pfx in url_prefixes]):
            log.debug("Local file: %s", pkg)
            return pkg

        cls._initialize()
        try:
            url = pkg
            log.info('Fetching remote file %s', url)
            req = requests.get(url)
            req.raise_for_status()
            if req.status_code != requests.codes.ok:
                log.error("Can't download {}".format(url))
                return False

            filename = urlsplit(req.url).path.rsplit('/', 1)[1]
            if 'content-disposition' in req.headers:
                _, params = cgi.parse_header(req.headers['content-disposition'])
                if 'filename' in params and params['filename']:
                    filename = params['filename']
            pkg = cls.tmpdir + '/' + filename
            with open(pkg, 'wb') as filed:
                for chunk in req.iter_content(4096):
                    filed.write(chunk)
            cls.backmap[pkg] = url
            return pkg
        except Exception as err:  # pylint: disable=broad-except
            log.error('Downloading error %s: %s', url, str(err))
        return None

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
