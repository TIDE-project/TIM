"""Routes for qst (question) plugin."""
import json
import re
from typing import Dict, Any, NamedTuple, Optional
from xml.sax.saxutils import quoteattr

import yaml
from flask import Blueprint
from flask import Response
from flask import abort
from flask import request

from timApp.plugin.containerLink import convert_md
from timApp.markdown.dumboclient import DumboOptions
from timApp.plugin.plugin import Plugin, PluginException
from timApp.plugin.plugin import get_num_value
from timApp.plugin.plugin import get_value
from timApp.util.flask.requesthelper import verify_json_params
from timApp.util.flask.responsehelper import json_response
from timApp.auth.sessioninfo import get_current_user_object
from timApp.document.docinfo import DocInfo
from timApp.lecture.askedjson import normalize_question_json

from timApp.plugin.containerLink import prepare_for_dumbo_attr_list_recursive, get_plugin_regex_obj

qst_plugin = Blueprint('qst_plugin',
                       __name__,
                       url_prefix='')  # TODO: Better URL prefix.


class QuestionInDocument(NamedTuple):
    markup: Dict
    qst: bool
    taskId: Optional[str]
    docId: int
    parId: str


@qst_plugin.route("/qst/mcq/reqs/")
@qst_plugin.route("/qst/mcq/reqs")
def qst_mcq_reqs():
    reqs = {
        "type": "embedded",
        "js": [
            # "tim/controllers/qstController",
               ],
        "angularModule": [],
        "multihtml": True,
        "multimd": True
    }

    return json_response(reqs)


@qst_plugin.route("/qst/mmcq/reqs/")
@qst_plugin.route("/qst/mmcq/reqs")
def qst_mmcq_reqs():
    reqs = {
        "type": "embedded",
        "js": [
            # "tim/controllers/qstController",
               ],
        "angularModule": [],
        "multihtml": True,
        "multimd": True
    }

    return json_response(reqs)


@qst_plugin.route("/qst/reqs/")
@qst_plugin.route("/qst/reqs")
def qst_reqs():
    reqs = {
        "type": "embedded",
        "js": [
            # "tim/controllers/qstController",
               ],
        "angularModule": [],
        "multihtml": True,
        "multimd": True
    }

    return json_response(reqs)


@qst_plugin.route("/qst/mcq/answer/", methods=["PUT"])
def qst_mcq_answer():
    jsondata = request.get_json()
    convert_mcq_to_qst(jsondata)
    return qst_answer_jso(jsondata)


@qst_plugin.route("/qst/mmcq/answer/", methods=["PUT"])
def qst_mmcq_answer():
    jsondata = request.get_json()
    convert_mcq_to_qst(jsondata, True)
    return qst_answer_jso(jsondata)


@qst_plugin.route("/qst/answer/", methods=["PUT"])
def qst_answer():
    return qst_answer_jso(request.get_json())


def qst_answer_jso(jsondata):
    tim_info = {}
    answers = jsondata['input']['answers']
    spoints = jsondata['markup'].get('points')
    markup = jsondata['markup']
    if spoints:
        points_table = create_points_table(spoints)
        points = calculate_points_from_json_answer(answers, points_table)
        minpoints = markup.get('minpoints', -1e20)
        maxpoints = markup.get('maxpoints', 1e20)
        if points < minpoints:
            points = minpoints
        if points > maxpoints:
            points = maxpoints
        tim_info["points"] = points
    convert_md([jsondata], options=DumboOptions.default())  # TODO get mathtype from doc settings?
    info = jsondata['info']
    result = False
    if info and info['max_answers'] and info['max_answers'] <= info.get('earlier_answers', 0) + 1:
        result = True
    if not result:
        markup = None

    save = answers
    web = {'result': "Vastattu", 'markup': markup, 'show_result': result, 'state': save}
    return json_response({'save': save, 'web': web, "tim_info": tim_info})


def is_review(request):
    # print(query)
    result = request.full_path.find("review=") >= 0
    return result


@qst_plugin.route("/qst/multihtml/", methods=["POST"])
def qst_multihtml():
    jsondata = request.get_json()
    multi = []
    for jso in jsondata:
        multi.append(qst_get_html(jso, is_review(request)))
    return json_response(multi)


def copy_value(name, qjso, jsom, defvalue = None):
    v = jsom.get(name, defvalue)
    if v:
        qjso[name] = v


def convert_mcq_to_qst(jso, is_mmcq = False):
    jsom = jso.get("markup")
    qjso = {}
    jso["markup"] = qjso
    qjso["questionText"] = jsom.get("stem", "")
    qjso["questionTitle"] = jsom.get("stem", "")
    qjso["stem"] = jsom.get("headerText", "Check your understanding")
    qjso["answerFieldType"] = "radio";
    qjso["isTask"] = True;
    copy_value("answerLimit", qjso, jsom, "1")
    copy_value("header", qjso, jsom)
    copy_value("footer", qjso, jsom)
    copy_value("button", qjso, jsom)
    copy_value("buttonText", qjso, jsom)
    if is_mmcq:
        qjso["questionType"] = "true-false";
        true_text = jsom.get("trueText", "True")
        false_text = jsom.get("falseText", "False")
        qjso["headers"] = [true_text, false_text];
        state = jso.get("state", None)
        if isinstance(state, list) and state:
            item = state[0]
            if not isinstance(item, list):
                new_state = [];
                n = 1
                for item in state:
                    new_item = []
                    if item == True:
                        new_item = ["1"]
                    if item == False:
                        new_item = ["2"]
                    new_state.append(new_item)
                jso["state"] = new_state
    else:
        qjso["questionType"] = "radio-vertical";
        qjso["headers"] = [];
        state = jso.get("state", None)
        if isinstance(state, int):
            jso["state"] = [[str(state+1)]]

    rows = [];
    qjso["rows"] = rows;
    choices = jsom.get("choices", [])
    for c in choices:
        rows.append(c.get("text", ""))
    expl = {};
    qjso["expl"] = expl;
    i = 1
    for c in choices:
        expl[str(i)] = c.get("reason", "")
        i += 1
    points = ""
    i = 1
    sep = ""
    for c in choices:
        cor = c.get("correct", False)
        if cor:
            points += sep + str(i)+":1"
            sep = ";"
        i += 1
    qjso["points"] = points


@qst_plugin.route("/qst/mcq/multihtml/", methods=["POST"])
def qst__mcq_multihtml():
    jsondata = request.get_json()
    multi = []
    for jso in jsondata:
        convert_mcq_to_qst(jso)
        multi.append(qst_get_html(jso, is_review(request)))
    return json_response(multi)


@qst_plugin.route("/qst/mmcq/multihtml/", methods=["POST"])
def qst__mmcq_multihtml():
    jsondata = request.get_json()
    multi = []
    for jso in jsondata:
        convert_mcq_to_qst(jso, True)
        multi.append(qst_get_html(jso, is_review(request)))
    return json_response(multi)


@qst_plugin.route("/qst/multimd/", methods=["POST"])
def qst_multimd():
    jsondata = request.get_json()
    multi = []
    for jso in jsondata:
        multi.append(qst_get_md(jso))
    return json_response(multi)


@qst_plugin.route("/qst/mcq/multimd", methods=["POST"])
@qst_plugin.route("/qst/mcq/multimd/", methods=["POST"])
def qst_mcq_multimd():
    jsondata = request.get_json()
    multi = []
    for jso in jsondata:
        multi.append(mcq_get_md(jso))
    return json_response(multi)


@qst_plugin.route("/qst/mmcq/multimd", methods=["POST"])
@qst_plugin.route("/qst/mmcq/multimd/", methods=["POST"])
def qst_mmcq_multimd():
    jsondata = request.get_json()
    multi = []
    for jso in jsondata:
        multi.append(mmcq_get_md(jso))
    return json_response(multi)


@qst_plugin.route("/qst/getQuestionMD/", methods=['POST'])
def get_question_md():
    md, = verify_json_params('text')
    markup = json.loads(md)
    plugin_data = {'markup': markup}
    prepare_for_dumbo_attr_list_recursive(get_plugin_regex_obj('qst'), plugin_data)
    convert_md([plugin_data], options=DumboOptions.default())

    return json_response({'md': plugin_data['markup']})


@qst_plugin.route("/qst/html/", methods=["POST"])
def qst_html():
    jsondata = request.get_json()

    html = qst_get_html(jsondata, is_review(request))
    return Response(html, mimetype="text/html")


@qst_plugin.route("/qst/<path:path>")
def not_found(path):
    """This 404 route is required because qst plugin is in the same process - otherwise calling a non-existent qst route
    results in a weird request loop, at least when running locally.
    """
    return abort(404)


def delete_key(d: Dict[str, Any], key: str):
    if key in d:
        del d[key]


def set_explanation(markup):
    # if expl, change to 1-based, if xpl rename to expl
    if 'xpl' in markup:
        markup['expl'] = markup.pop('xpl')
        return
    if 'expl' not in markup:
        return
    expl = markup['expl']
    xpl = {}
    markup['expl'] = xpl
    for key in expl:
        try:
            n = int(key)
            xpl[n + 1] = expl[key]
        except ValueError:
            pass


NOLAZY = "<!--nolazy-->"


def qst_str(state):
    s = str(state)
    s = s.replace("], ", "\n")
    s = s.replace("]", "")
    s = s.replace("[", "")
    s = s.replace("''", "-")
    s = s.replace("'", "")
    return s


def mcq_get_md(jso):
    """
    Gives question in format:
        \mcq{Onko kuu}{Valitse tosi lause}
        {|l l|}
        {
        \hline $\bigcirc$ & Kuu on lähempänä kuin aurinko \\
        \hline $\bigcirc$ & Kuu on yhtä iso kuin aurinko \\
        \hline $\bigcirc$ & Kuu on juustoa \\
        \hline
        }

    :param jso: json block to make the markdown or TeX
    :param review:
    :return:
    """
    info = jso['info']
    markup = jso['markup']
    printlikeqst = get_value(markup, 'texprintlikeqst', 0)
    user_print = jso.get('userPrint', False)

    header = markup.get('header', markup.get('headerText', 'Check your understanding'))
    footer = markup.get('footer', '')
    stem = markup.get('stem', '')
    texcolumns = markup.get('texcolumns', '|l l|' if not printlikeqst else 'l L')
    user_answer = jso.get('state', None)
    if user_answer is None:
        user_print = False
    if user_print:
        texcolumns = markup.get('texusercolumns', '|l l l|' if not printlikeqst else 'l L L')
    texhline = markup.get('texhline', '\\hline' if not printlikeqst else '')
    if texhline:
        texhline += ' '
    choices = markup.get('choices', [])
    cstr = ''
    idx = 0
    for choice in choices:
        user_mark = ''
        correct = choice.get('correct', False)
        reason = ''
        checked = ' '
        if user_print:
            reason = ' & ' + choice.get('reason', '')
            if idx == user_answer:
                user_mark = ' \, \\cmark' if correct else ' \, \\xmark'
                checked = '*'
        line = texhline + '\\radiobutton' + checked + user_mark + '& ' + choice.get('text', '') + reason + ' \\\\\n'
        cstr += line
        idx += 1

    if cstr and texhline:
        cstr += texhline + '\n'

    if printlikeqst:
        result = f'''
\\qsty{{{header}}}{{{stem}}}
{{{''}}}
{{{texcolumns}}}
{{
{cstr}
}}
{{{footer}}}
'''
    else:
        result = f'''
\\mcq{{{header}}}{{{stem}}}
{{{texcolumns}}}
{{
{cstr}
}}
'''

    return result


def mmcq_get_md(jso):
    """
    Gives question in format:
        \mcq{Onko kuu}{Valitse tosi lause}
        {|l l|}
        {
        \hline $\bigcirc$ & Kuu on lähempänä kuin aurinko \\
        \hline $\bigcirc$ & Kuu on yhtä iso kuin aurinko \\
        \hline $\bigcirc$ & Kuu on juustoa \\
        \hline
        }

    :param jso: json block to make the markdown or TeX
    :param review:
    :return:
    """
    info = jso['info']
    markup = jso['markup']
    user_print = jso.get('userPrint', False)
    printlikeqst = get_value(markup, 'texprintlikeqst', 0)

    header = markup.get('header', markup.get('headerText', 'Check your understanding'))
    footer = markup.get('footer', '')
    stem = markup.get('stem', '')
    true_text = markup.get('trueText', 'True')
    false_text = markup.get('falseText', 'False')
    correct_mark = markup.get('texcorrectText', '\\cmark')
    wrong_mark = markup.get('texwrongText', '\\xmark')

    texcolumns = markup.get('texcolumns', '|l c c|' if not printlikeqst else 'L c c')
    user_answer = jso.get('state', [])
    if not user_answer:
        user_print = False
    if user_print:
        texcolumns = markup.get('texusercolumns', '|l c c c l|' if not printlikeqst else 'L c c c L')
    texhline = markup.get('texhline', '\\hline' if not printlikeqst else '')
    if texhline:
        texhline += ' '
    choices = markup.get('choices', [])
    reason = ' & ' + ' ' + ' & ' + ' ' if user_print else ''
    cstr = texhline + ' & ' + true_text + ' & ' + false_text + reason + ' \\\\\n'
    idx = 0
    for choice in choices:
        correct = choice.get('correct', False)
        reason = ''
        leftbox = '\\checkbox'
        rightbox = '\\checkbox'
        if user_print and user_answer:
            ua = None
            if len(user_answer) > idx:
                ua = user_answer[idx]
            correct_or_wrong_mark = correct_mark if ua == correct else wrong_mark
            if ua:
                leftbox += '*'
            # noinspection PySimplifyBooleanCheck
            if ua == False:   # do not replace with not ua because it can be None
                rightbox += '*'
            reason = ' & & '
            if ua is not None:
                reason = ' & ' + correct_or_wrong_mark + ' & ' + choice.get('reason', '')
        line = texhline + choice.get('text', '') + '& ' + leftbox + ' & ' + rightbox + reason + ' \\\\\n'
        cstr += line
        idx += 1

    if cstr and texhline:
        cstr += texhline + '\n'

    if printlikeqst:
        result = f'''
\\qsty{{{header}}}{{{stem}}}
{{{''}}}
{{{texcolumns}}}
{{
{cstr}
}}
{{{footer}}}
    '''
    else:
        result = f'''
\\mcq{{{header}}}{{{stem}}}
{{{texcolumns}}}
{{
{cstr}
}}
'''

    return result


qst_attrs = {'button', 'buttonText', 'footer', 'header', 'isTask', 'lazy', 'resetText', 'stem', }


def qst_get_html(jso, review):
    result = False
    info = jso['info']
    markup = jso['markup']
    markup = normalize_question_json(markup,
                                     allow_top_level_keys=
                                     qst_attrs)
    jso['markup'] = markup
    if info and info['max_answers'] and info['max_answers'] <= info.get('earlier_answers', 0):
        result = True
    if not result:
        delete_key(markup, 'points')
        delete_key(markup, 'expl')
    jso['show_result'] = result

    if review:
        usercode = qst_str(jso.get("state", "-"))
        s = ""
        result = NOLAZY + '<div class="review" ng-non-bindable><pre>' + usercode + '</pre>' + s + '</div>'
        return result

    attrs = json.dumps(jso)

    runner = 'qst-runner'
    s = f'<{runner} json={quoteattr(attrs)}></{runner}>'
    return s


def qst_get_md(jso):
    result = False
    info = jso['info']
    markup = jso['markup']
    points_table = create_points_table(markup.get('points'))

    set_explanation(markup)
    jso['show_result'] = result

    # attrs = json.dumps(jso)
    usercode = qst_str(jso.get("state", "-"))
    user_print = jso.get('userPrint', False)

    print_reason = get_num_value(info,'max_answers', 1) <= get_num_value(info,'earlier_answers', 0)

    header = markup.get('header', '')
    footer = markup.get('footer', '')
    texboxw = markup.get('texboxw', '0.2')
    texboxh = markup.get('texboxh', '10')
    stem = markup.get('stem', '')
    stem += '\par' if stem else ''
    qjson = markup  # .get('json',{})
    question_text = qjson.get('questionText', '')
    question_type = qjson.get('questionType', '')
    vertical = question_type.find('vertical') >= 0
    headers = qjson.get('headers', [])

    texcolumns = markup.get('texcolumns', 'l L' if vertical else '')
    user_answer = jso.get('state', [])
    if not user_answer:
        user_print = False
    if user_print:
        texcolumns = markup.get('texusercolumns', 'l L L' if vertical else '')
    texhline = markup.get('texhline', '')
    if texhline:
        texhline += ' '
    rows = qjson.get('rows', [])
    reason = ' & ' + ' ' + ' & ' + ' ' if user_print else ''
    cstr = texhline + ' & ' + reason + ' \\\\\n'
    cstr = ''
    expl = markup.get('expl', {})
    empty_theader = True
    theader = ' &'
    sep = ''
    tc = ' '
    for h in headers:
        if h:
            empty_theader = False
        theader += sep + h
        sep = ' & '
        tc += 'c '
    if user_print:
        if not texcolumns:
            texcolumns = 'L' + tc + 'L'
    else:
        if not texcolumns:
            texcolumns = 'L' + tc

    aft = qjson.get('answerFieldType', '')
    boxdefault = ''
    leftbox = '\\radiobutton'
    if aft == 'checkbox':
        leftbox = '\\checkbox'
    if aft == 'text':
        leftbox = '\\ttextbox{' + str(texboxw) + '}'
        boxdefault = '{\\vspace{' + str(texboxh) + 'mm}}'

    idx = 0
    for row in rows:
        if type(row) is not str:
            continue
        correct = '' # choice.get('correct', False)
        exp = expl.get(str(idx+1),'')
        reason = ''
        lbox = ''
        sep = ''
        lh = len(headers)
        if lh == 0:
            lh = 1
        for i in range(0, lh):
            box = leftbox
            uidx = 0 if vertical else idx
            ui = idx if vertical else i
            cell_points = 0
            boxdef = boxdefault
            if user_print and user_answer:
                ua = uidx < len(user_answer) and str(ui+1) in user_answer[uidx]
                if len(points_table) > uidx:
                    cell_points = get_num_value(points_table[uidx], str(ui + 1), 0)
                correct_or_wrong_mark = ''
                box = leftbox
                if aft == 'text':
                    if idx < len(user_answer):
                        uar = user_answer[idx]
                        if i < len(uar):
                            ua = uar[i]
                            if ua:
                                boxdef = '{' + ua + '}'
                    box += boxdef
                else:
                    if ua:
                        box += '*'
                    if cell_points > 0:
                        box = "\correct{" + box + "}"
                    if cell_points:
                        box = "\lbpoints{" + str(cell_points) + "}{" + box + "}"
            else:
                box += boxdef
            lbox += sep + box
            sep = " & "
        reason = ' '
        if user_print and print_reason:  # user_answer:
            reason = ' & ' + exp
        if vertical:
            line = texhline + lbox + ' & ' + row + reason + ' \\\\\n'
        else:
            line = texhline + row + ' & ' + lbox + reason + ' \\\\\n'
        cstr += line
        idx += 1

    if cstr and texhline:
        cstr += texhline + '\n'

    if not empty_theader:
        cstr = theader + ' \\\\\n' + texhline + '\n' + cstr

    result = f'''
\\qsty{{{header}}}{{{stem}}}
{{{question_text}}}
{{{texcolumns}}}
{{
{cstr}
}}
{{{footer}}}
    '''

    return result


def question_convert_js_to_yaml(markup: Dict, is_task: bool, task_id: Optional[str]):
    # save question. How to pick up question see lecture.py, get_question_data_from_document
    markup = normalize_question_json(markup, allow_top_level_keys=qst_attrs)
    question_title = markup["questionTitle"]
    question_title = question_title.replace('"', '').replace("'", '')
    # taskid = questionTitle.replace(" ", "")  # TODO: make better conversion to ID
    taskid = question_title.replace("md:", "")
    taskid = re.sub('[^A-Za-z0-9]', '', taskid)
    if task_id:
        taskid = task_id
    qst = is_task
    delete_key(markup, "question")  # old attribute
    delete_key(markup, "taskId")
    delete_key(markup, "qst")

    mdyaml = yaml.dump(markup, encoding='utf-8', allow_unicode=True, default_flow_style=False).decode(
        'utf-8')  # see also .safe_dump
    mdyaml = mdyaml.replace("\n\n", "\n")
    # mdyaml = mdyaml.replace("\\xC4", "Ä").replace("\\xD6", "Ö").replace(
    #    "\\xC5", "Å").replace("\\xE4", "ä").replace("\\xF6", "ö").replace("\\xE5", "å")
    prefix = ' '
    if qst:
        prefix = ' d'  # like document question
    # result = '``` {#' + taskid + prefix + 'question="' + question + '" plugin="qst"}\n' + mdyaml + '```\n'
    result = '``` {#' + taskid + prefix + 'question="' + 'true' + '" plugin="qst"}\n' + mdyaml + '```\n'
    return result


def get_question_data_from_document(d: DocInfo, par_id: str, edit=False) -> QuestionInDocument:
    """
    Get markup for question

    :param d: document
    :param par_id: paragraph id
    :param edit: is purposu to edit data or show data
    :return: markup for question
    """
    # pick up question from document, for saving question see edit.py question_convert_js_to_yam
    # par_id might be like 100.Ruksit.SpQA0NX2itOd  and one must cut the beginin
    i = par_id.rfind(".")
    if i >= 0:
        par_id = par_id[i + 1:]
    par = d.document.get_paragraph(par_id)
    try:
        plugin_values = Plugin.from_paragraph(par, user=get_current_user_object()).values
    except PluginException:
        return abort(400, f'Paragraph is not a plugin: {par_id}')
    plugindata = {'markup': plugin_values}
    markup = plugindata.get('markup')
    if ( markup.get("choices", None) ):
        convert_mcq_to_qst(plugindata, par.get_attr('plugin', '').find('mmcq') == 0)
    if not edit or edit == 'false':
        settings = d.document.get_settings()
        prepare_for_dumbo_attr_list_recursive(get_plugin_regex_obj('qst'), plugindata)
        convert_md([plugindata], options=par.get_dumbo_options(base_opts=settings.get_dumbo_options()))
    markup = plugindata.get('markup')
    return QuestionInDocument(
        markup=normalize_question_json(markup, allow_top_level_keys=qst_attrs),
        qst=not par.is_question(),
        taskId=par.get_attr('taskId'),
        docId=d.id,
        parId=par_id,
    )


def create_points_table(points):
    points_table = []
    if points and points != '':
        points_split = points.split('|')
        for row in points_split:
            row_points = row.split(';')
            row_points_dict = {}
            for col in row_points:
                if col != '':
                    col_points = col.split(':', 2)
                    if len(col_points) == 1:
                        row_points_dict[col_points[0]] = 1
                    else:
                        row_points_dict[col_points[0]] = float(col_points[1])
            points_table.append(row_points_dict)
    return points_table


def calculate_points_from_json_answer(single_answers, points_table):
    points = 0.0
    for (oneAnswer, point_row) in zip(single_answers, points_table):
        for oneLine in oneAnswer:
            if oneLine in point_row:
                points += point_row[oneLine]
    return points


def calculate_points(answer, points_table):
    # single_answers = []
    # all_answers = answer.split('|')
    # for answer in all_answers:
    #    single_answers.append(answer.split(','))

    single_answers = json.loads(answer)
    return calculate_points_from_json_answer(single_answers, points_table)
