# -*- coding: utf-8 -*-
import json
from functools import lru_cache

import requests
from requests.exceptions import Timeout

from documentmodel.docparagraphencoder import DocParagraphEncoder
from plugin import PluginException

TIM_URL = ""

CSPLUGIN_NAME = 'csPlugin'
SVNPLUGIN_NAME = 'showFile'
HASKELLPLUGIN_NAME = 'haskellplugins2'
PALIPLUGIN_NAME = 'pali'

PLUGINS = {
    "csPlugin":      {"host": "http://" + CSPLUGIN_NAME + ":5000/cs/"},
    "taunoPlugin":   {"host": "http://" + CSPLUGIN_NAME + ":5000/cs/tauno/"},
    "simcirPlugin":  {"host": "http://" + CSPLUGIN_NAME + ":5000/cs/simcir/"},
    "csPluginRikki": {"host": "http://" + CSPLUGIN_NAME + ":5000/cs/rikki/"},  # demonstrates a broken plugin
    "showCode":      {"host": "http://" + SVNPLUGIN_NAME + ":5000/svn/", "browser": False},
    "showImage":     {"host": "http://" + SVNPLUGIN_NAME + ":5000/svn/image/", "browser": False},
    "showVideo":     {"host": "http://" + SVNPLUGIN_NAME + ":5000/svn/video/", "browser": False},
    "mcq":           {"host": "http://" + HASKELLPLUGIN_NAME + ":5001/"},
    "mmcq":          {"host": "http://" + HASKELLPLUGIN_NAME + ":5002/"},
    "shortNote":     {"host": "http://" + HASKELLPLUGIN_NAME + ":5003/"},
    "graphviz":      {"host": "http://" + HASKELLPLUGIN_NAME + ":5004/", "browser": False},
    # "pali":          {"host": "http://" + PALIPLUGIN_NAME + ":5000/"}
}


def call_plugin_generic(plugin, method, route, data=None, headers=None):
    plug = get_plugin(plugin)
    try:
        request = requests.request(method, plug['host'] + route + "/", data=data, timeout=15, headers=headers)
        request.encoding = 'utf-8'
        return request.text
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
        raise PluginException("Could not connect to plugin.")


def call_plugin_html(plugin, info, state, task_id=None):
    plugin_data = json.dumps({"markup": info, "state": state, "taskID": task_id}, cls=DocParagraphEncoder)
    return call_plugin_generic(plugin,
                               'post',
                               'html',
                               data=plugin_data,
                               headers={'Content-type': 'application/json'})


def call_plugin_multihtml(plugin, plugin_data):
    return call_plugin_generic(plugin,
                               'post',
                               'multihtml',
                               data=json.dumps(plugin_data, cls=DocParagraphEncoder),
                               headers={'Content-type': 'application/json'})


def call_plugin_resource(plugin, filename):
    try:
        plug = get_plugin(plugin)
        request = requests.get(plug['host'] + filename, timeout=5, stream=True)
        request.encoding = 'utf-8'
        return request
    except requests.exceptions.Timeout:
        raise PluginException("Could not connect to plugin: " + plugin)


def call_plugin_answer(plugin, answer_data):
    return call_plugin_generic(plugin,
                               'put',
                               'answer',
                               json.dumps(answer_data, cls=DocParagraphEncoder),
                               headers={'Content-type': 'application/json'})


# Get lists of js and css files required by plugin, as well as list of Angular modules they define.
@lru_cache(maxsize=100)
def plugin_reqs(plugin):
    return call_plugin_generic(plugin, 'get', 'reqs')


# Gets plugin info (host)
def get_plugin(plugin):
    if plugin in PLUGINS:
        return PLUGINS[plugin]
    raise PluginException("Plugin does not exist.")


# Get address towards which the plugin must send its further requests, such as answers
def get_plugin_tim_url(plugin):
    if plugin in PLUGINS:
        return TIM_URL + "/" + plugin
    raise PluginException("Plugin does not exist.")


def get_plugin_needs_browser(plugin):
    # if not plugin: return False
    plg = get_plugin(plugin)
    if "browser" not in plg: return True
    return plg["browser"] != False
