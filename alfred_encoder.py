# encoding: utf-8

import json
import sys


class AlfredResult:
    def __init__(self, title, subtitle, arg, icon=None, _type='default'):
        if not icon:
            icon = {}

        self.title = title
        self.subtitle = subtitle
        self.arg = arg
        self.icon = icon
        self.type = _type


class AlfredResultEncoder(json.JSONEncoder):
    def default(self, o):
        return o.__dict__


class AlfredResultList:
    alfred_dic = {'items': []}

    def append(self, alfred_result):
        self.alfred_dic['items'].append(alfred_result)

    def send_to_alfred(self, cache):
        for item in self.alfred_dic['items']:
            try:
                thumbnail_name = "{}.png".format(int(item.arg))
                if cache.exists(thumbnail_name):
                    item.icon['path'] = cache.get_path(thumbnail_name)
            except Exception:
                item.icon['path'] = item.arg

        sys.stdout.write(json.dumps(
            self.alfred_dic, cls=AlfredResultEncoder, indent=4) + "\n")
