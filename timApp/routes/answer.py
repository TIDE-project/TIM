"""Answer-related routes."""
from datetime import timezone
from typing import Union

from flask import Blueprint

import containerLink
from options import get_option
from plugin import Plugin, PluginException
from timdb.blocktypes import blocktypes
from timdb.models.block import Block
from timdb.tim_models import AnswerUpload, Answer
from .common import *


answers = Blueprint('answers',
                    __name__,
                    url_prefix='')


def is_answer_valid(plugin, old_answers, tim_info):
    """Determines whether the currently posted answer should be considered valid.

    :param plugin: The plugin object to which the answer was posted.
    :param old_answers: The old answers for this task for the current user.
    :param tim_info: The tim_info structure returned by the plugin or None.
    :return: True if the answer should be considered valid, False otherwise.
    """
    answer_limit = plugin.answer_limit()
    if answer_limit is not None and (answer_limit <= len(old_answers)):
        return False, 'You have exceeded the answering limit.'
    if plugin.starttime(default=datetime(1970, 1, 1, tzinfo=timezone.utc)) > datetime.now(timezone.utc):
        return False, 'You cannot submit answers yet.'
    if plugin.deadline(default=datetime.max.replace(tzinfo=timezone.utc)) < datetime.now(timezone.utc):
        return False, 'The deadline for submitting answers has passed.'
    if tim_info.get('notValid', None):
        return False, 'Answer is not valid'

    return True, 'ok'


@answers.route("/savePoints/<int:user_id>/<int:answer_id>", methods=['PUT'])
def save_points(answer_id, user_id):
    answer, _ = verify_answer_access(answer_id, user_id, require_teacher_if_not_own=True)
    doc_id, task_id_name, _ = Plugin.parse_task_id(answer['task_id'])
    points, = verify_json_params('points')
    try:
        plugin = Plugin.from_task_id(answer['task_id'])
    except PluginException as e:
        return abort(400, str(e))
    a = Answer.query.get(answer_id)
    try:
        points = points_to_float(points)
    except ValueError:
        abort(400, 'Invalid points format.')
    try:
        a.points = plugin.validate_points(points) if not has_teacher_access(doc_id) else points
    except PluginException as e:
        abort(400, str(e))
    a.last_points_modifier = getCurrentUserGroup()
    db.session.commit()
    return okJsonResponse()


def points_to_float(points: Union[str, float]):
    if points:
        points = float(points)
    else:
        points = None
    return points


@answers.route("/<plugintype>/<task_id_ext>/answer/", methods=['PUT'])
def post_answer(plugintype: str, task_id_ext: str):
    """
    Saves the answer submitted by user for a plugin in the database.

    :param plugintype: The type of the plugin, e.g. csPlugin.
    :param task_id_ext: The extended task id of the form "22.palidrome.par_id".
    :return: JSON
    """
    timdb = getTimDb()
    doc_id, task_id_name, _ = Plugin.parse_task_id(task_id_ext)
    task_id = str(doc_id) + '.' + str(task_id_name)
    verify_task_access(doc_id, task_id_name)
    if 'input' not in request.get_json():
        return jsonResponse({'error': 'The key "input" was not found from the request.'}, 400)
    answerdata = request.get_json()['input']

    answer_browser_data = request.get_json().get('abData', {})
    is_teacher = answer_browser_data.get('teacher', False)
    save_teacher = answer_browser_data.get('saveTeacher', False)
    save_answer = answer_browser_data.get('saveAnswer', False) and task_id_name
    if save_teacher:
        verify_teacher_access(doc_id)
    users = None
    if not save_answer or is_teacher:
        verify_seeanswers_access(doc_id)
    if is_teacher:
        answer_id = answer_browser_data.get('answer_id', None)
        if answer_id is not None:
            expected_task_id = timdb.answers.get_task_id(answer_id)
            if expected_task_id != task_id:
                return abort(400, 'Task ids did not match')
            users = timdb.answers.get_users(answer_id)
            if len(users) == 0:
                return abort(400, 'No users found for the specified answer')
            user_id = answer_browser_data.get('userId', None)
            if user_id not in users:
                return abort(400, 'userId is not associated with answer_id')
    try:
        plugin = Plugin.from_task_id(task_id_ext)
    except PluginException as e:
        return abort(400, str(e))

    if plugin.type != plugintype:
        abort(400, 'Plugin type mismatch: {} != {}'.format(plugin.type, plugintype))

    upload = None
    if isinstance(answerdata, dict):
        file = answerdata.get('uploadedFile', '')
        trimmed_file = file.replace('/uploads/', '')
        if trimmed_file:
            # The initial upload entry was created in /pluginUpload route, so we need to check that the owner matches
            # what the browser is saying. Additionally, we'll associate the answer with the uploaded file later
            # in this route.
            block = Block.query.filter((Block.description == trimmed_file) & (Block.type_id == blocktypes.UPLOAD)).first()
            if block is None:
                abort(400, 'Non-existent upload: {}'.format(trimmed_file))
            verify_view_access(block.id, message="You don't have permission to touch this file.")
            upload = AnswerUpload.query.filter(AnswerUpload.upload_block_id == block.id).first()
            if upload.answer_id is not None:
                abort(400, 'File was already uploaded: {}'.format(file))

    # Load old answers
    current_user_id = getCurrentUserId()

    if users is None:
        users = [u['id'] for u in get_session_users()]

    old_answers = timdb.answers.get_common_answers(users, task_id)

    # Get the newest answer (state). Only for logged in users.
    state = pluginControl.try_load_json(old_answers[0]['content']) if logged_in() and len(old_answers) > 0 else None

    plugin.values['current_user_id'] = getCurrentUserName()
    plugin.values['user_id'] = ';'.join([timdb.users.get_user(uid)['name'] for uid in users])
    plugin.values['look_answer'] = is_teacher and not save_teacher

    timdb.close()

    answer_call_data = {'markup': plugin.values, 'state': state, 'input': answerdata, 'taskID': task_id}

    try:
        plugin_response = containerLink.call_plugin_answer(plugintype, answer_call_data)
        jsonresp = json.loads(plugin_response)
    except ValueError:
        return jsonResponse({'error': 'The plugin response was not a valid JSON string. The response was: ' +
                                      plugin_response}, 400)
    except PluginException:
        return jsonResponse({'error': 'The plugin response took too long'}, 400)

    if 'web' not in jsonresp:
        return jsonResponse({'error': 'The key "web" is missing in plugin response.'}, 400)
    result = {'web': jsonresp['web']}

    def addReply(obj, key):
        if key not in plugin.values: return
        textToAdd = plugin.values[key]
        obj[key] = textToAdd

    addReply(result['web'], '-replyImage')
    addReply(result['web'], '-replyMD')
    addReply(result['web'], '-replyHTML')
    if 'save' in jsonresp:
        save_object = jsonresp['save']
        tags = []
        tim_info = jsonresp.get('tim_info', {})
        points = tim_info.get('points', None)
        multiplier = plugin.points_multiplier()
        if multiplier and points is not None:
            points *= plugin.points_multiplier()
        elif not multiplier:
            points = None
        # Save the new state
        try:
            tags = save_object['tags']
        except (TypeError, KeyError):
            pass
        if not is_teacher and save_answer:
            is_valid, explanation = is_answer_valid(plugin, old_answers, tim_info)
            points_given_by = None
            if answer_browser_data.get('giveCustomPoints'):
                try:
                    points = plugin.validate_points(answer_browser_data.get('points'))
                except PluginException as e:
                    result['error'] = str(e)
                else:
                    points_given_by = getCurrentUserGroup()
            if points or save_object or tags:
                result['savedNew'], saved_answer_id = timdb.answers.saveAnswer(users,
                                                          task_id,
                                                          json.dumps(save_object),
                                                          points,
                                                          tags,
                                                          is_valid,
                                                          points_given_by)
            else:
                result['savedNew'], saved_answer_id = False, None
            if not is_valid:
                result['error'] = explanation
        elif save_teacher:
            if current_user_id not in users:
                users.append(current_user_id)
            points = answer_browser_data.get('points', points)
            points = points_to_float(points)
            result['savedNew'], saved_answer_id = timdb.answers.saveAnswer(users,
                                                                           task_id,
                                                                           json.dumps(save_object),
                                                                           points,
                                                                           tags,
                                                                           valid=True,
                                                                           points_given_by=getCurrentUserGroup())
        else:
            result['savedNew'], saved_answer_id = False, None
        if result['savedNew'] and upload is not None:
            # Associate this answer with the upload entry
            upload.answer_id = saved_answer_id
            db.session.commit()

    return jsonResponse(result)


def get_hidden_name(user_id):
    return 'Undisclosed student %d' % user_id


def should_hide_name(doc_id, user_id):
    return not getTimDb().users.has_teacher_access(user_id, doc_id) and user_id != getCurrentUserId()


@answers.route("/taskinfo/<task_id>")
def get_task_info(task_id):
    try:
        plugin = Plugin.from_task_id(task_id)
    except PluginException as e:
        return abort(400, str(e))
    tim_vars = {'maxPoints': plugin.max_points(),
                'userMin': plugin.user_min_points(),
                'userMax': plugin.user_max_points(),
                'deadline': plugin.deadline(),
                'starttime': plugin.starttime(),
                'answerLimit': plugin.answer_limit()}
    return jsonResponse(tim_vars)


@answers.route("/answers/<task_id>/<user_id>")
def get_answers(task_id, user_id):
    try:
        user_id = int(user_id)
    except ValueError:
        abort(404, 'Not a valid user id')
    verifyLoggedIn()
    timdb = getTimDb()
    try:
        doc_id, _, _ = Plugin.parse_task_id(task_id)
    except PluginException as e:
        return abort(400, str(e))
    if not timdb.documents.exists(doc_id):
        abort(404, 'No such document')
    user = timdb.users.get_user(user_id)
    if user_id != getCurrentUserId():
        verify_seeanswers_access(doc_id)
    if user is None:
        abort(400, 'Non-existent user')
    user_answers = timdb.answers.get_answers(user_id, task_id)
    if hide_names_in_teacher(doc_id):
        for answer in user_answers:
            for c in answer['collaborators']:
                if should_hide_name(doc_id, c['user_id']):
                    c['real_name'] = get_hidden_name(c['user_id'])
    return jsonResponse(user_answers)


@answers.route("/allDocumentAnswersPlain/<int:doc_id>")
def get_document_answers(doc_id):
    doc = Document(doc_id)
    pars = doc.get_dereferenced_paragraphs()
    task_ids, _ = pluginControl.find_task_ids(pars)
    get_all_answers_as_list(task_ids)
    return get_all_answers_list_plain(task_ids)


# TODO Remove misleading route ("HTML")
@answers.route("/allAnswersHtml/<task_id>")
@answers.route("/allAnswersPlain/<task_id>")
def get_all_answers_plain(task_id):
    return get_all_answers_list_plain([task_id])


def get_all_answers_list_plain(task_ids: List[str]):
    all_answers = get_all_answers_as_list(task_ids)
    text = "\n\n----------------------------------------------------------------------------------\n".join(all_answers)
    return Response(text, mimetype='text/plain')


def get_all_answers_as_list(task_ids: List[str]):
    verifyLoggedIn()
    timdb = getTimDb()
    doc_ids = set()
    for t in task_ids:
        doc_id, _, _ = Plugin.parse_task_id(t)
        doc_ids.add(doc_id)
    usergroup = request.args.get('group')
    age = request.args.get('age')
    valid = request.args.get('valid', '1')
    printname = request.args.get('name', False)
    printname = printname == "true"

    if not usergroup:
        usergroup = None

    hide_names = False
    for doc_id in doc_ids:
        if not timdb.documents.exists(doc_id):
            abort(404, 'No such document: {}'.format(doc_id))
        # Require full teacher rights for getting all answers
        verify_teacher_access(doc_id)
        hide_names = hide_names or hide_names_in_teacher(doc_id)
    all_answers = timdb.answers.get_all_answers(task_ids, usergroup, hide_names, age, valid, printname)
    return all_answers


@answers.route("/allAnswers/<task_id>")
def get_all_answers(task_id):
    all_answers = get_all_answers_as_list(task_id)
    return jsonResponse(all_answers)


@answers.route("/getState")
def get_state():
    timdb = getTimDb()
    _, par_id, user_id, answer_id = unpack_args('doc_id',
                                                'par_id',
                                                'user_id',
                                                'answer_id', types=[int, str, int, int])
    plugin_params = {}
    review = get_option(request, 'review', False)
    if review:
        plugin_params['review'] = True

    answer, doc_id = verify_answer_access(answer_id, user_id)

    doc = Document(doc_id)
    block = doc.get_paragraph(par_id)
    user = timdb.users.get_user(user_id)
    if user is None:
        abort(400, 'Non-existent user')

    texts, js_paths, css_paths, modules = pluginControl.pluginify(doc,
                                                                  [block],
                                                                  user,
                                                                  timdb,
                                                                  custom_state=answer['content'])

    [reviewhtml], _, _, _ = pluginControl.pluginify(doc,
                                                    [block],
                                                    user,
                                                    timdb,
                                                    custom_state=answer['content'],
                                                    plugin_params=plugin_params,
                                                    wrap_in_div=False) if review else ([None], None, None, None)

    return jsonResponse({'html': texts[0]['html'], 'reviewHtml': reviewhtml['html'] if review else None})


def verify_answer_access(answer_id, user_id, require_teacher_if_not_own=False):
    timdb = getTimDb()
    answer = timdb.answers.get_answer(answer_id)
    if answer is None:
        abort(400, 'Non-existent answer')
    doc_id, _, _ = Plugin.parse_task_id(answer['task_id'])
    if not timdb.documents.exists(doc_id):
        abort(404, 'No such document')
    # TODO: Check the ref_from parameter
    if user_id != getCurrentUserId() or not logged_in():
        if require_teacher_if_not_own:
            verify_teacher_access(doc_id)
        else:
            verify_seeanswers_access(doc_id)
    else:
        verify_view_access(doc_id)
        if not any(a['user_id'] == user_id for a in answer['collaborators']):
            abort(403, "You don't have access to this answer.")
    return answer, doc_id


@answers.route("/getTaskUsers/<task_id>")
def get_task_users(task_id):
    doc_id, _, _ = Plugin.parse_task_id(task_id)
    verify_seeanswers_access(doc_id)
    usergroup = request.args.get('group')
    users = getTimDb().answers.get_users_by_taskid(task_id)
    if usergroup is not None:
        timdb = getTimDb()
        users = [user for user in users if timdb.users.is_user_id_in_group(user['id'], usergroup)]
    if hide_names_in_teacher(doc_id):
        for user in users:
            if should_hide_name(doc_id, user['id']):
                user['name'] = '-'
                user['real_name'] = get_hidden_name(user['id'])
    return jsonResponse(users)
