from bs4 import BeautifulSoup
from containerLink import callPlugin
from containerLink import pluginReqs
import re
import json

# Receive html-string with plugin in it, 
# extract values from contents
def prepPluginCall(htmlStr):
    tree = BeautifulSoup(htmlStr)
    plugins = []
    for node in tree.find_all('pre'):
        values = {}
        name = node['plugin']
        try:
            values["identifier"] = node['id']
        except KeyError:
            values['identifier'] = " "
        if(len(node.text) > 0):
            multiLineId = ""
            multiLineVal = ""
            multiLineCont = False
            for value in node.string.strip().split('\n'):
                if("=====" in value):
                    values[multiLineId] = multiLineVal
                    multiLineId = ""
                    multiLineVal = ""
                    multiLineCont = False
                elif(multiLineCont):
                    multiLineVal = multiLineVal + "\n" + value
                elif(":" in value):  # If line does not contain valid value pair, discard it.
                    pair = value.strip().split(':',1)
                    values[pair[0].strip()] = pair[1].strip()
                elif("=" in value):
                    multiLineCont = True
                    pair = value.split("=", 1)
                    multiLineId = pair[0]
                    multiLineVal = multiLineVal + pair[1]
                    
        plugins.append({"plugin": name, "values": values})
    return plugins


# Take a set of blocks and search for plugin markers,
# replace contents with plugin.
def pluginify(blocks,user): 
    preparedBlocks = []
    plugins = []
    for block in blocks:
        if("plugin=" in block and "<code>" in block):
            pluginInfo = prepPluginCall(block)
            for pair in pluginInfo:
                plugins.append(pair['plugin'])
                pair['values']["user_id"] =  user
                pluginHtml = callPlugin(pair['plugin'], pair['values'])
                rx = re.compile('<code>.*</code>')
                block = rx.sub(block, pluginHtml)
                preparedBlocks.append(block)
        else:
            preparedBlocks.append(block)
    return (plugins,preparedBlocks)

# pluginReqs is json of required files
def pluginDeps(pluginReqs):
    js = []
    jsMods = []
    css = [] 
    for f in pluginReqs:
        if "CSS" in f:
            for cssF in f['CSS']:
                css.append(cssF)
        if "JS" in f:
            for jsF in f['JS']:
                js.append(jsF)
        if "angularModule" in f:
            for ng in f['angularModule']:
                jsMods.append(ng)
    return (js,css, jsMods)


def getPluginDatas(plugins):
    jsPaths = []
    cssPaths = []
    modules = ["\"ngSanitize\",", "\"angularFileUpload\","]
    i = 0
    for p in plugins: 
        try:
            (rawJs,rawCss,modsList) = pluginDeps(json.loads(pluginReqs(p)))      
            for src in rawJs:
                if( "http" in src):
                    jsPaths.append(src)
                else:
                    x = getPlugin(p)['host']
                    jsPaths.append(x + src)
            for cssSrc in rawCss:
                if( "http" in src):
                    cssPaths.append(cssSrc)
                else:
                    x = getPlugin(p)['host']
                    cssPaths.append(x + src)
            for mod in modsList:
                modules.append("\""+mod+"\"")
        except: 
            continue
    return (jsPaths, cssPaths, modules)





