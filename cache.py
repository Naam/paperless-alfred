# encoding: utf-8

from threading import Thread
import requests
from os import path, makedirs


class PaperlessCache():
    _dir = ""
    _threads = []

    def __init__(self, service):
        cache_dir = path.join(path.expanduser('~/Library/Caches'), service)
        if not path.exists(cache_dir):
            makedirs(cache_dir)
        self._dir = cache_dir

    def _cache_download(self, token, url, name):
        auth_header = {'Authorization': "Token " + token}
        result = requests.get(url, headers=auth_header)
        download_path = path.join(path.curdir, self._dir, name)
        open(download_path, 'wb').write(result.content)

    def cache_item(self, token, url, name):
        thread = Thread(target=self._cache_download, args=(token, url, name))
        self._threads.append(thread)
        thread.start()

    def exists(self, name):
        return path.exists(path.join(self._dir, name))

    def get_path(self, item):
        return path.join(self._dir, item)

    def sync(self):
        [thread.join() for thread in self._threads]

    def __del__(self):
        self.sync()
