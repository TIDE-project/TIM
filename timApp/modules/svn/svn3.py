# -*- coding:utf-8 -*-

# server to get a file from selected range
# Get parameters (every param can have n after, f.ex file1=)
# file    = URL for file to get
# start   = regexp that much match to start printing (default = first line)
#   startcnt= int: how many times the start must match before start (default=1)
#   startn  = int: how many lines to move print forward or backward from start-point (default = 0)
#   end     = regexp to stop printing (default = last line)
#   endcnt  = int: how many times the end must match before end (default=1)
#   endn    = int: how many lines to move end forward or backward from end-point (default = 0)
#   linefmt = format for line number, f.exe linefmt={0:03d}%20 (default = "")
#   maxn    = max number of lines to print (default=10000)
#   lastn   = last linenumber to print (default=1000000)
#   url     = if 1, use same url as last file (default=)
#   include = after this file is printied, print this text, \n is new  line (default="")
#   replace = replace every line that match this, by the by-parameter (default="")
#   by      = by what text is the replace replaced (\n is new line), (default="")
#
# Examples
#    ?file=http://example.org/Hello.java&start=main&end=}       -> print from main to first }
#    ?file=http://example.org/Hello.java                        -> print whole file
#    ?file=http://example.org/Hello.java&start=startn=1&endn=-1 -> print file except first and last line
#    ?file=http://example.org/Hello.java&start=main&end=.       -> print only the first line where is main
#    ?file=http://example.org/Hello.java&start=main&end=.&endn=1
#                                                  -> print only the first line where is main and next line
#
import http.server
import socketserver
import time
import math
import sys
import os

import json

import re

sys.path.insert(0, '/py')  # /py on mountattu docker kontissa /opt/tim/timApp/modules/py -hakemistoon

from fileParams import get_param, get_surrounding_headers2, is_user_lazy, add_lazy, NOLAZY, get_clean_param, \
    replace_template_param, replace_template_params, query_params_to_map_check_parts, encode_json_data, make_lazy, \
    get_params, do_headers, post_params, multi_post_params, get_chache_keys, clear_cache, get_template, join_dict, \
    get_all_templates, file_to_string, get_file_to_output, get_surrounding_md_headers, get_surrounding_headers, \
    get_surrounding_md_headers2, QueryClass

PORT = 5000

csstatic = '/service/timApp/modules/cs/static/'

regx_hm = re.compile(r"[ ,/;:.hm]")


def timestr_2_sec2(value):
    # compare to timestr_2_sec, this is slower
    if not value:
        return 0
    if isinstance(value, int):
        return value
    s = "0 0 0 " + str(value).replace("s", "")  # loppu s unohdetaan muodosta 1h3m2s
    s = regx_hm.sub(" ", s)
    s = s.strip()
    sc = s.split(" ")
    n = len(sc)
    h = int(sc[n - 3])
    m = int(sc[n - 2])
    s = int(sc[n - 1])
    return h * 3600.0 + m * 60.0 + s * 1.0


def take_last_number(s, i):
    n = 0
    k = 1
    c = '0'
    while i >= 0:  # pass non numbers
        c = s[i]
        if '0' <= c <= '9':
            break
        i -= 1
    while i >= 0:
        n += int(c) * k
        k *= 10
        i -= 1
        if i < 0:
            break
        c = s[i]
        if c < '0' or '9' < c:
            break

    return n, i


def timestr_2_sec(value):
    # Tämän ratkaisun vaikutus: 100 000 small videota alku ja loppuajalla
    #  start: 53
    #  end: 59          1.2 s
    #  end: "59"        1.27
    #  end: "23:45:59"  1.5 s
    #  timestr_2_sec2   1.8 s
    if not value:
        return 0
    if isinstance(value, int):
        return value
    st = str(value)
    if st.isdigit():
        return int(st)
    i = len(st) - 1
    s, i = take_last_number(st, i)
    m, i = take_last_number(st, i)
    h, i = take_last_number(st, i)
    return h * 3600.0 + m * 60.0 + s * 1.0


def sec_2_timestr(t: float):
    # tt = time.gmtime(t) jne on todella hidas
    if not t:
        return ""
    h = math.floor(t / 3600)
    t = (t - h * 3600)
    m = math.floor(t / 60)
    s = int((t - m * 60))
    if not h:
        h = ""
    else:
        h = str(h) + "h"
    if not h and not m:
        m = ""
    else:
        m = str(m) + "m"
    s = str(s) + "s"
    return h + m + s


def get_image_md(query):
    """Muodostaa kuvan näyttämiseksi tarvittavan MD-koodin.

    :param query: pyynnön paramterit
    :return: kuvan md-jono

    """
    url = get_clean_param(query, "file", "")
    w = get_clean_param(query, "width", "")
    h = get_clean_param(query, "height", "")
    if w:
        w = 'width=' + w + ' '
    if h:
        h = 'height=' + h + ' '
    header, footer = get_surrounding_md_headers2(query, "pluginHeader", None)
    result = header + "\n\n" + "![{0}]({1}){{{2}{3}}}".format(footer, url, w, h)
    return result


def get_image_html(query):
    """Muodostaa kuvan näyttämiseksi tarvittavan HTML-koodin.

    :param query: pyynnön paramterit
    :return: kuvan html-jono

    """
    url = get_clean_param(query, "file", "")
    w = get_clean_param(query, "width", "")
    h = get_clean_param(query, "height", "")
    if w:
        w = 'width="' + w + '" '
    if h:
        h = 'height="' + h + '" '
    header, footer = get_surrounding_headers2(query)
    result = header + '<img ' + w + h + 'src="' + url + '">' + footer
    if is_user_lazy(query):
        return add_lazy(result) + header + footer
    return NOLAZY + result


def replace_time_params(query, htmlstr):
    start = timestr_2_sec(get_param(query, "start", ""))
    end = timestr_2_sec(get_param(query, "end", ""))
    startt = sec_2_timestr(start)
    if startt:
        startt = ", " + startt
    s = htmlstr.replace("{{startt}}", startt)
    duration = sec_2_timestr(end - start)
    if duration != "":
        duration = "(" + duration + ") "
    s = s.replace("{{duration}}", duration)
    return s


def small__and_list_html(query, duration_template):
    s = replace_template_param(query, '{{stem}}', "stem")
    di = replace_template_param(query, ' {{videoname}}', "videoname")
    if di:
        dur = replace_time_params(query, duration_template)
        icon = replace_template_param(
            query, '<span><img src="{{videoicon}}" alt="Click here to show" /> </span> ',
            "videoicon", "/csstatic/video_small.png")
        s += ' <a class="videoname">' + icon + di + dur + '</a>'
    di = replace_template_param(query, ' {{doctext}}', "doctext")
    if di:
        icon = replace_template_param(
            query, '<span><img src="{{docicon}}"  alt="Go to doc" /> </span>', "docicon", "/csstatic/book.png")
        s += ' <a href="" target="timdoc">' + icon + di + '</a>'
    return s


def small_and_list_md(query, duration_template):
    s = replace_template_param(query, '{{stem}}', "stem")
    di = replace_template_param(query, ' {{videoname}}', "videoname")
    if di:
        dur = replace_time_params(query, duration_template)
        icon = replace_template_param(
            query, ' \\includegraphics[width=0.1in]{{{{videoicon}}}}',
            "videoicon", csstatic + "video_small.png")
        s += '' + icon + di + ' ' + dur + ''
    di = replace_template_param(query, ' {{doctext}}', "doctext")
    if di:
        icon = replace_template_param(
            query, '\\includegraphics[width=0.1in]{{{{docicon}}}}', "docicon", csstatic + "book.png")
        s += ' ' + icon + di + ''
    return s


def small_video_html(query):
    # Kokeiltu myös listoilla, ei mitattavasti parempi
    s = '<div class="smallVideoRunDiv">'
    s += replace_template_param(query, "<h4>{{header}}</h4>", "header")
    s += '<p>' + small__and_list_html(query, "{{duration}}") + '</p>'
    s += replace_template_param(query, '<div><p></p></div><p class="plgfooter">{{footer}}</p>', "footer")
    s += '</div>'

    return s


def list_video_html(query):
    s = '<div class="listVideoRunDiv">'
    s += replace_template_param(query, '<h4>{{header}}</h4>', "header")
    s += '<ul><li>' + small__and_list_html(query, "{{startt}} {{duration}}") + '</li></ul>'
    s += replace_template_param(query, '<div ><p></p></div><p class="plgfooter">{{footer}}</p>', "footer")
    s += '</div>'
    return s


def video_html(query):
    s = '<div class="videoRunDiv">'
    s += replace_template_param(query, '<h4>{{header}}</h4>', "header")
    s += replace_template_param(query, '<p class="stem" >{{stem}}</p>', "stem")
    s += '<div ><p></p></div>' \
        '<div class="no-popup-menu">' \
        '<img src="/csstatic/video.png"  width="200" alt="Click here to show the video" />' \
        '</div>'
    di = replace_template_param(query, ' {{doctext}}', "doctext")
    if di:
        icon = replace_template_param(
            query, '<span><img src="{{docicon}}"  alt="Go to doc" /> </span>', "docicon", "/csstatic/book.png")
        s += ' <a href="" target="timdoc">' + icon + di + '</a>'
    s += replace_template_params(query, '<p class="plgfooter">{{footer}}</p>', "footer")
    s += '</div>'
    return s


def get_video_html(query: QueryClass):
    """Muodostaa videon näyttämiseksi tarvittavan HTML-koodin.

    :param query: pyynnön paramterit
    :return: videon html-jono

    """
    iframe = get_param(query, "iframe", False) or True
    js = query_params_to_map_check_parts(query)
    jso = json.dumps(js)

    video_type = get_param(query, "type", "icon")
    # print ("iframe " + iframe + " url: " + url)
    video_app = True
    encoded = encode_json_data(jso)
    if video_type == "small":
        # s = string_to_string_replace_attribute(
        #     '<small-video-runner \n##QUERYPARAMS##\n></small-video-runner>', "##QUERYPARAMS##", query)
        s = f'<small-video-runner json="{encoded}"></list-video-runner>'
        s = make_lazy(s, query, small_video_html)
        return s
    if video_type == "list":
        #  s = string_to_string_replace_attribute(
        #     '<list-video-runner \n##QUERYPARAMS##\n></list-video-runner>', "##QUERYPARAMS##", query)
        s = f'<list-video-runner json="{encoded}"></list-video-runner>'
        s = make_lazy(s, query, list_video_html)
        return s
    if video_app:
        # s = string_to_string_replace_attribute(
        #    '<video-runner \n##QUERYPARAMS##\n></video-runner>', "##QUERYPARAMS##", query)
        s = f'<video-runner json="{encoded}"></list-video-runner>'
        s = make_lazy(s, query, video_html)
        return s

    url = get_clean_param(query, "file", "")
    w = get_clean_param(query, "width", "")
    h = get_clean_param(query, "height", "")
    if w:
        w = 'width="' + w + '" '
    if h:
        h = 'height="' + h + '" '

    if iframe:
        return '<iframe class="showVideo" src="' + url + '" ' + w + h + 'autoplay="false" ></iframe>'

        #  result = '<video class="showVideo"
        #      src="' + url + '" type="video/mp4" ' + w + h + 'autoplay="false" controls="" ></video>'
    result = '<video class="showVideo" ng-cloak src="' + url + '" type="video/mp4" ' + w + h + ' controls="" ></video>'
    return result


def small_video_md(query):
    # Kokeiltu myös listoilla, ei mitattavasti parempi
    s = '\\smallVideoRunDiv{'
    s += replace_template_param(query, '\\pluginHeader{{{{header}}}}\n\n', "header")
    s += '' + small_and_list_md(query, "{{duration}}") + ''
    s += replace_template_params(query, '\\plgfooter{{{{footer}}}}\n', "footer")
    s += '}'
    return s


def list_video_md(query):
    s = '\\listVideoRunDiv{'
    s += replace_template_param(query, '\\pluginHeader{{{{header}}}}\n\n', "header")
    s += '\\begin{itemize}\n\\item\n' + small_and_list_md(query, "{{startt}} {{duration}}") + '\\end{itemize}\n'
    s += replace_template_params(query, '\\plgfooter{{{{footer}}}}\n', "footer")
    s += '}'
    return s


def video_md(query):
    s = '\\videoRunDiv{'
    s += replace_template_param(query, '\\pluginHeader{{{{header}}}}\n\n', "header")
    s += replace_template_param(query, '\\stem{{{{stem}}}}\n', "stem")
    s += '''
\\begin{figure}[H]
\\centering
\\includegraphics[width=1.5in]{/service/timApp/modules/cs/static/video.png}
\\end{figure}
'''
    di = replace_template_param(query, ' {{doctext}}', "doctext")
    # if di:
    #    icon = replace_template_param(
    #        query, '<span><img src="{{docicon}}"  alt="Go to doc" /> </span>', "docicon", "/csstatic/book.png")
    #    s += ' <a href="" target="timdoc">' + icon + di + '</a>'
    s += replace_template_params(query, '\\plgfooter{{{{footer}}}}\n', "footer")
    s += '}'
    return s


def get_video_md(query):
    """Muodostaa videon näyttämiseksi tarvittavan MD-koodin.

    :param query: pyynnön paramterit
    :return: videon html-jono

    """
    iframe = get_param(query, "iframe", False) or True
    js = query_params_to_map_check_parts(query)
    jso = json.dumps(js)

    video_type = get_param(query, "type", "icon")
    # print ("iframe " + iframe + " url: " + url)
    video_app = True
    if video_type == "small":
        s = small_video_md(query)
        return s
    if video_type == "list":
        s = list_video_md(query)
        return s
    if video_app:
        s = video_md(query)
        return s

    url = get_clean_param(query, "file", "")
    w = get_clean_param(query, "width", "")
    h = get_clean_param(query, "height", "")
    if w:
        w = 'width="' + w + '" '
    if h:
        h = 'height="' + h + '" '

    if iframe:
        return '<iframe class="showVideo" src="' + url + '" ' + w + h + 'autoplay="false" ></iframe>'

        #  result = '<video class="showVideo"
        #      src="' + url + '" type="video/mp4" ' + w + h + 'autoplay="false" controls="" ></video>'
    result = '<video class="showVideo" ng-cloak src="' + url + '" type="video/mp4" ' + w + h + ' controls="" ></video>'
    return result


class TIMShowFileServer(http.server.BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        self.send_response(200, "ok")
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header("Access-Control-Allow-Headers", "X-Requested-With, Content-Type")
        print(self.path)
        print(self.headers)

    def do_GET(self):
        self.do_all(get_params(self))

    def do_POST(self):
        if self.path.find('/test') >= 0:
            do_headers(self, "application/json")

            dummy, n = (self.path + "&n=1").split("n=", 1)
            n, dummy = (n + "&").split("&", 1)
            try:
                n = int(n)
            except ValueError:
                n = 1
            t1 = time.clock()
            query = post_params(self)
            # self.do_all(query)

            s = ''
            for i in range(0, n):
                s = get_html(self, query, True)

            t2 = time.clock()
            ts = "%7.4f" % (t2 - t1)
            self.wout(s + "\n" + ts)
            print(ts)
            return

        multimd = self.path.find('/multimd') >= 0

        if self.path.find('/multihtml') < 0 and not multimd:
            self.do_all(post_params(self))
            return

        print("do_POST MULTIHML ==========================================")
        t1 = time.clock()
        querys = multi_post_params(self)
        # print(querys)

        do_headers(self, "application/json")

        htmls = []
        for query in querys:
            if multimd:
                s = get_md(self, query)
            else:
                s = get_html(self, query, True)
            htmls.append(s)

        sresult = json.dumps(htmls)
        self.wout(sresult)
        t2 = time.clock()
        ts = "multihtml: %d - %7.4f" % (len(querys), (t2 - t1))
        print(ts)

    def do_PUT(self):
        self.do_all(post_params(self))

    def wout(self, s):
        self.wfile.write(s.encode("UTF-8"))

    def do_all(self, query: QueryClass):
        # print(self.path)
        # print(self.headers)
        # print query

        show_html = self.path.find('/html') >= 0
        is_template = self.path.find('/template') >= 0
        is_css = self.path.find('/css') >= 0
        is_js = self.path.find('/js') >= 0  or self.path.find('.ts') >= 0
        is_reqs = self.path.find('/reqs') >= 0
        is_image = self.path.find('/image') >= 0
        is_video = self.path.find('/video') >= 0
        is_pdf = self.path.find('/pdf') >= 0

        content_type = 'text/plain'
        if is_reqs:
            content_type = "application/json"
        if show_html:
            content_type = 'text/html; charset=utf-8'
        if is_css:
            content_type = 'text/css'
        if is_js:
            content_type = 'application/javascript'

        do_headers(self, content_type)

        if self.path.find("refresh") >= 0:
            self.wout(get_chache_keys())
            clear_cache()
            return

        tempdir = "svn"
        if is_image:
            tempdir = "image"
        if is_video:
            tempdir = "video"
        if is_pdf:
            tempdir = "pdf"
        tempdir = "templates/" + tempdir

        if is_template:
            tempfile = get_param(query, "file", "")
            tidx = get_param(query, "idx", "0")
            print("tempfile: ", tempfile, tidx)
            return self.wout(get_template(tempdir, tidx, tempfile))

        if is_reqs:
            result_json = join_dict({"multihtml": True, "multimd": True}, get_all_templates(tempdir))
            if is_video or is_pdf:
                result_json.update({"js": ["/svn/js/video.js"], "angularModule": ["videoApp"]})
            result_str = json.dumps(result_json)
            self.wout(result_str)
            return

        if is_css:
            # printFileTo('cs.css',self.wfile)
            return

        if is_js:
            # print(content_type)
            filereq = self.path
            filereq = os.path.basename(filereq)
            if self.path.find('.ts') < 0:
                filereq = 'build/' + filereq
            self.wout(file_to_string('js/' + filereq))
            # self.wout(file_to_string(self.path))
            return

        s = get_html(self, query, show_html)
        self.wout(s)
        return


def get_md(self, query):
    is_image = self.path.find('/image/') >= 0
    is_video = self.path.find('/video/') >= 0
    is_pdf = self.path.find('/pdf/') >= 0
    is_template = self.path.find('/template') >= 0
    tempfile = get_param(query, "file", "")

    if is_image:
        if is_template:
            return file_to_string('templates/image/' + tempfile)
        s = get_image_md(query)
        return s

    if is_video:
        if is_template:
            return file_to_string('templates/video/' + tempfile)
        s = get_video_md(query)
        return s

    if is_pdf:
        if is_template:
            return file_to_string('templates/pdf/' + tempfile)
        s = get_video_md(query)
        return s

    # Was none of special, so print the file(s) in query

    cla = get_param(query, "class", "")
    w = get_param(query, "width", "")
    if w:
        w = ' style="width:' + w + '"'
    if cla:
        cla = " " + cla

    s = ""

    s += get_file_to_output(query, False)
    filename = query.jso.get('markup',{}).get('file','')
    name = filename[filename.rfind('/')+1:]
    s = get_surrounding_md_headers(query, s, '\\smallhref{' + filename + '}{' + name +'}')
    return s


def get_html(self: http.server.BaseHTTPRequestHandler, query: QueryClass, show_html: bool):
    is_image = self.path.find('/image/') >= 0
    is_video = self.path.find('/video/') >= 0
    is_pdf = self.path.find('/pdf/') >= 0
    is_template = self.path.find('/template') >= 0
    tempfile = get_param(query, "file", "")

    if is_image:
        if is_template:
            return file_to_string('templates/image/' + tempfile)
        s = get_image_html(query)
        return s

    if is_video:
        if is_template:
            return file_to_string('templates/video/' + tempfile)
        s = get_video_html(query)
        return s

    if is_pdf:
        if is_template:
            return file_to_string('templates/pdf/' + tempfile)
        s = get_video_html(query)
        return s

    # Was none of special, so print the file(s) in query

    cla = get_param(query, "class", "")
    w = get_param(query, "width", "")
    if w:
        w = ' style="width:' + w + '"'
    if cla:
        cla = " " + cla

    s = ""
    ffn = get_param(query, "file", "")
    fn = ffn
    i = ffn.rfind("/")
    if i >= 0:
        fn = ffn[i + 1:]

    if show_html:
        s += '<pre ng-non-bindable class="showCode' + cla + '"' + w + '>'
    s += get_file_to_output(query, show_html)
    if show_html:
        s += '</pre><p class="smalllink"><a href="' + ffn + '" target="_blank">' + fn + '</a>'
    s = NOLAZY + get_surrounding_headers(query, s)  # TODO: korjaa tähän mahdollisuus lazyyyn, oletus on ei.
    return s

'''
def keep_running():
    return True

def run_while_true(server_class=http.server.HTTPServer,
                   handler_class=http.server.BaseHTTPRequestHandler):
    """
    This assumes that keep_running() is a function of no arguments which
    is tested initially and after each request.  If its return value
    is true, the server continues.
    """
    server_address = ('', PORT)
    httpd = server_class(server_address, handler_class)
    while keep_running():
        httpd.handle_request()

if __name__ == '__main__':
    run_while_true(handler_class=TIMShowFileServer)
    print("svn-plugin waiting for requests...")
'''


# Kun debuggaa Windowsissa, pitää vaihtaa ThreadingMixIn
# Jos ajaa Linuxissa ThreadingMixIn, niin chdir vaihtaa kaikkien hakemistoa?
# Ongelmaa korjattu siten, että kaikki run-kommennot saavat prgpathin käyttöönsä

# if __debug__:
# if True:
class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    """Handle requests in a separate thread."""

print("Debug mode/ThreadingMixIn")
#
# else:
#    class ThreadedHTTPServer(socketserver.ForkingMixIn, http.server.HTTPServer):
#        """Handle requests in a separate thread."""
#    print("Normal mode/ForkingMixIn")


if __name__ == '__main__':
    server = ThreadedHTTPServer(('', PORT), TIMShowFileServer)
    print('Starting ShowFileServer, use <Ctrl-C> to stop')
    server.serve_forever()
