import json
import threading
import time
from datetime import timezone, datetime
from random import randrange

import dateutil.parser
from flask import Blueprint, render_template
from flask import Response
from flask import abort
from flask import current_app
from flask import request
from flask import session

from timApp.accesshelper import verify_ownership, get_doc_or_abort, verify_edit_access
from timApp.common import has_ownership, \
    get_user_settings
from timApp.dbaccess import get_timdb
from timApp.documentmodel.randutils import hashfunc
from timApp.requesthelper import get_option, verify_json_params
from timApp.responsehelper import json_response, ok_response
from timApp.routes.login import log_in_as_anonymous
from timApp.routes.qst import get_question_data_from_document, delete_key, create_points_table, \
    calculate_points_from_json_answer, calculate_points
from timApp.sessioninfo import get_current_user_id, logged_in, get_current_user_name
from timApp.tim_app import app
from timApp.timdb.models.docentry import DocEntry
from timApp.timdb.tempdb_models import TempDb, Runningquestion
from timApp.timdb.tim_models import db, Message, LectureUsers, AskedQuestion, LectureAnswer, Lecture

lecture_routes = Blueprint('lecture',
                           __name__,
                           url_prefix='')


@lecture_routes.route('/getLectureInfo')
def get_lecture_info():
    """Route to get info from lectures.

    Gives answers, and messages and other necessary info.

    """
    if not request.args.get("lecture_id"):
        abort(400, "Bad request, missing lecture id")
    lecture_id = int(request.args.get("lecture_id"))
    messages = get_all_messages(lecture_id)
    timdb = get_timdb()
    question_ids = []
    answerers = []

    is_lecturer = False
    current_user = get_current_user_id()
    if timdb.lectures.get_lecture(lecture_id).lecturer== current_user:
        is_lecturer = True

    if is_lecturer:
        answer_dicts = timdb.lecture_answers.get_answers_to_questions_from_lecture(lecture_id)
    else:
        answer_dicts = timdb.lecture_answers.get_user_answers_to_questions_from_lecture(lecture_id, current_user)

    added_users = []
    for singleDict in answer_dicts:
        if singleDict['question_id'] not in question_ids:
            question_ids.append(singleDict['question_id'])
        if singleDict['user_id'] not in added_users:
            added_users.append(singleDict['user_id'])
            answerers.append({'name': singleDict['user_name'], 'id': singleDict['user_id']})

    lecture_questions = timdb.questions.get_multiple_asked_questions(question_ids)

    return json_response(
        {"messages": messages, "answerers": answerers, "answers": answer_dicts, "questions": lecture_questions,
         "isLecturer": is_lecturer})


@lecture_routes.route('/getLectureAnswerTotals/<int:lecture_id>')
def get_lecture_answer_totals(lecture_id):
    is_lecturer = False
    current_user = get_current_user_id()
    timdb = get_timdb()
    if timdb.lectures.get_lecture(lecture_id).lecturer == current_user:
        is_lecturer = True
    results = timdb.lecture_answers.get_totals(lecture_id, None if is_lecturer else get_current_user_id())
    sum_field_name = get_option(request, 'sum_field_name', 'sum')
    count_field_name = get_option(request, 'count_field_name', 'count')

    def generate_text():
        for a in results:
            yield f'{a["name"]};{sum_field_name};{a["sum"]}\n'
        yield '\n'
        for a in results:
            yield f'{a["name"]};{count_field_name};{a["count"]}\n'
    return Response(generate_text(), mimetype='text/plain')


@lecture_routes.route('/getAllMessages')
def get_all_messages(param_lecture_id=-1):
    """Route to get all the messages from some lecture.

    Tulisi hakea myös kaikki aukiolevat kysymykset, joihin käyttäjä ei ole vielä vastannut.

    """
    if not request.args.get("lecture_id") and param_lecture_id is -1:
        abort(400, "Bad request, missing lecture id")
    timdb = get_timdb()
    if request.args.get("lecture_id"):
        lecture_id = int(request.args.get("lecture_id"))
    else:
        lecture_id = param_lecture_id

    # Prevents previously asked question to be asked from user and new questions from people who just came to lecture
    # current_user = get_current_user_id()
    # for triple in __question_to_be_asked:
    #     if triple[0] == lecture_id and current_user not in triple[2]:
    #         triple[2].append(current_user)

    messages = timdb.messages.get_messages(lecture_id)
    if len(messages) > 0:
        list_of_new_messages = []
        for message in messages:
            user = timdb.users.get_user(message.get('user_id'))
            time_as_time = message.get("timestamp")
            list_of_new_messages.append(
                {"sender": user.get('name'),
                 "time": time_as_time.strftime('%H:%M:%S'),
                 "message": message.get('message')})

        # When using this same method just to get the messages for lectureInfo
        if param_lecture_id is not -1:
            return list_of_new_messages

        return json_response(
            {"status": "results", "data": list_of_new_messages, "lastid": messages[-1].get('msg_id'),
             "lectureId": lecture_id})

    # When using this same method just to get the messages for lectureInfo
    if param_lecture_id is not -1:
        return []

    return json_response({"status": "no-results", "data": [], "lastid": -1, "lectureId": lecture_id})


@lecture_routes.route('/getUpdates')
def get_updates():
    # taketime("before update")
    ret = do_get_updates(request)
    # taketime("after update")
    return ret


def do_get_updates(request):
    """Gets updates from some lecture.

    Checks updates in 1 second frequently and answers if there is updates.

    """
    # if not request.args.get('client_message_id') or not request.args.get("lecture_id"):
    if not request.args.get('c') or not request.args.get("l"):
        abort(400, "Bad request")
    client_last_id = int(request.args.get('c'))  # client_message_id'))
    current_question_id = None
    current_points_id = None
    if 'i' in request.args:
        current_question_id = int(request.args.get('i'))  # current_question_id'))
    if 'p' in request.args:
        current_points_id = int(request.args.get('p')) # current_points_id'))

    use_wall = get_option(request, 'm', False)  # 'get_messages'
    session['use_wall'] = use_wall
    use_questions = get_option(request, 'q', False) # 'get_questions'
    session['use_questions'] = use_questions
    is_lecturer = get_option(request, 't', False)  # is_lecturer TODO: check from session

    helper = request.args.get("l")  # lecture_id
    if len(helper) > 0:
        lecture_id = int(float(helper))
    else:
        lecture_id = -1

    timdb = get_timdb()
    tempdb = get_tempdb()
    step = 0
    lecture = Lecture.query.get(lecture_id)


    doc_id = request.args.get("d")  # "doc_id"
    if doc_id:
        doc_id = int(doc_id)
    if not lecture or not check_if_lecture_is_running(lecture):
        timdb.lectures.delete_users_from_lecture(lecture_id)
        clean_dictionaries_by_lecture(lecture_id)
        return get_running_lectures(doc_id)

    list_of_new_messages = []
    last_message_id = -1

    lecturers = []
    students = []
    current_user = get_current_user_id()
    user_name = get_current_user_name()

    time_now = str(datetime.now(timezone.utc).strftime("%H:%M:%S"))
    tempdb.useractivity.update_or_add_activity(lecture_id, current_user, time_now)

    lecture_ending = 100
    options = lecture.options_parsed
    teacher_poll = options.get("teacher_poll", "")
    teacher_poll = teacher_poll.split(";")
    poll_interval_ms = 4000
    long_poll = False
    # noinspection PyBroadException
    try:
        poll_interval_ms = int(options.get("poll_interval", 4))*1000
        long_poll = bool(options.get("long_poll", False))
    except:
        pass

    # noinspection PyBroadException
    try:
        poll_interval_t_ms = int(options.get("poll_interval_t", 1))*1000
        long_poll_t = bool(options.get("long_poll_t", False))
    except:
        pass

    poll_interval_ms += randrange(-100,500)

    if teacher_poll:
        # noinspection PyBroadException
        try:
            if teacher_poll.index(user_name) >= 0:
                poll_interval_ms = poll_interval_t_ms
                long_poll = long_poll_t
        except:
            pass

    # Jos poistaa tämän while loopin, muuttuu long pollista perinteiseksi polliksi
    while step <= 10:
        if is_lecturer:
            lecturers, students = get_lecture_users(timdb, tempdb, lecture_id)
            poll_interval_ms = poll_interval_t_ms
            long_poll = long_poll_t
        # Gets new messages if the wall is in use.
        if use_wall:
            last_message = timdb.messages.get_last_message(lecture_id)
            if last_message:
                last_message_id = last_message[-1].get('msg_id')
                if last_message_id != client_last_id:
                    messages = timdb.messages.get_new_messages(lecture_id, client_last_id)
                    messages.reverse()

                    for message in messages:
                        user = timdb.users.get_user(message.get('user_id'))
                        time_as_time = message.get("timestamp")
                        list_of_new_messages.append(
                            {"sender": user.get('name'),
                             "time": time_as_time.strftime('%H:%M:%S'),
                             "message": message.get('message')})
                    last_message_id = messages[-1].get('msg_id')

        # Check if current question is still running and user hasn't already answered on it on another tab
        # Return also questions new end time if it is extended
        if current_question_id:
            resp = {"status": "results", "data": list_of_new_messages, "lastid": last_message_id,
                    "lectureId": lecture_id, "question": True, "e": True, "lecturers": lecturers, # e = isLecture
                    "students": students, "lectureEnding": lecture_ending,
                    "new_end_time": None, "ms": poll_interval_ms}

            question = tempdb.runningquestions.get_running_question_by_id(current_question_id)
            already_answered = tempdb.usersanswered.has_user_info(current_question_id, current_user)
            if question and not already_answered:
                already_extended = tempdb.usersextended.has_user_info(current_question_id, current_user)
                if not already_extended:
                    tempdb.usersextended.add_user_info(lecture_id, current_question_id, current_user)
                    # Return this is question has been extended
                    resp['new_end_time'] = question.end_time
                    return json_response(resp)
            else:
                # Return this if question has ended or user has answered to it
                return json_response(resp)

        if current_points_id:
            resp = {"status": "results", "data": list_of_new_messages, "lastid": last_message_id,
                    "lectureId": lecture_id, "question": True, "e": True, "lecturers": lecturers,  # e = isLecture
                    "students": students, "lectureEnding": lecture_ending,
                    "points_closed": True, "ms": poll_interval_ms}
            already_closed = tempdb.pointsclosed.has_user_info(current_points_id, current_user)
            if already_closed:
                return json_response(resp)

        # Gets new questions if the questions are in use.
        if use_questions:
            new_question = get_new_question(lecture_id, current_question_id, current_points_id)
            if new_question is not None:
                lecture_ending = check_if_lecture_is_ending(current_user, lecture)
                resp = {"status": "results", "data": list_of_new_messages, "lastid": last_message_id,
                        "lectureId": lecture_id, "e": True, "lecturers": lecturers,                # e = isLecture
                        "students": students, "lectureEnding": lecture_ending, "ms": poll_interval_ms}
                resp.update(new_question)
                return json_response(resp)

        if len(list_of_new_messages) > 0:
            if lecture and lecture.lecturer == current_user:
                lecture_ending = check_if_lecture_is_ending(current_user, lecture)
                lecturers, students = get_lecture_users(timdb, tempdb, lecture_id)
            return json_response(
                {"status": "results", "data": list_of_new_messages, "lastid": last_message_id,
                 "lectureId": lecture_id, "e": True, "lecturers": lecturers, "students": students, # e = isLecture
                 "lectureEnding": lecture_ending, "ms": poll_interval_ms})

        if not long_poll or current_app.config['TESTING']:
            # Don't loop when testing
            break
        # For long poll wait 1 sek before new check.
        time.sleep(1)
        step += 1

    if lecture and lecture.lecturer == current_user:
        lecture_ending = check_if_lecture_is_ending(current_user, lecture)

    if lecture_ending != 100 or len(lecturers) or len(students):
        return json_response(
            {"status": "no-results", "data": ["No new messages"], "lastid": client_last_id, "lectureId": lecture_id,
             "e": True, "lecturers": lecturers, "students": students,                                # e = isLecture
             "lectureEnding": lecture_ending, "ms": poll_interval_ms})

    return json_response({"e": -1, "ms": poll_interval_ms})  # no new updates                        # e = isLecture


@lecture_routes.route('/getQuestionManually')
def get_question_manually():
    """Route to use to get question manually (instead of getting question in /getUpdates)."""
    if not request.args.get('lecture_id'):
        abort(400, "Bad request")
    lecture_id = int(request.args.get('lecture_id'))
    new_question = get_new_question(lecture_id, None, None, True)
    return json_response(new_question)


def get_new_question(lecture_id, current_question_id=None, current_points_id=None, force=False):
    """
    :param current_points_id: TODO: what is this?
    :param current_question_id: The id of the current question.
    :param lecture_id: lecture to get running questions from
    :param force: Return question, even if it already has been shown to user
    :return: None if no questions are running
             dict with data of new question if there is a question running and user hasn't answered to that question.
             {'already_answered': True} if there is a question running and user has answered to that.
    """
    timdb = get_timdb()
    tempdb = get_tempdb()
    current_user = get_current_user_id()
    question = tempdb.runningquestions.get_lectures_running_questions(lecture_id)
    if question:
        question = question[0]
        asked_id = question.asked_id
        already_shown = tempdb.usersshown.has_user_info(asked_id, current_user)
        already_answered = tempdb.usersanswered.has_user_info(asked_id, current_user)
        if already_answered:
            if force:
                return {'already_answered': True}
            else:
                return None
        if (not already_shown or force) or (asked_id != current_question_id):
            question_json = timdb.questions.get_asked_question(asked_id)[0]["json"]
            answer = timdb.lecture_answers.get_user_answer_to_question(asked_id, current_user)
            tempdb.usersshown.add_user_info(lecture_id, asked_id, current_user)
            tempdb.usersextended.add_user_info(lecture_id, asked_id, current_user)
            if answer:
                answer = answer[0]['answer']
            else:
                answer = ''
            return {'question': True, 'askedId': question.asked_id, 'asked': question.ask_time, 'questionjson': question_json,
                    "answer": answer}
    else:
        question_to_show_points = tempdb.showpoints.get_currently_shown_points(lecture_id)
        if question_to_show_points:
            asked_id = question_to_show_points[0].asked_id
            already_shown = tempdb.pointsshown.has_user_info(asked_id, current_user)
            already_closed = tempdb.pointsclosed.has_user_info(asked_id, current_user)
            if already_closed:
                if force:
                    tempdb.pointsclosed.delete_user_info(lecture_id, asked_id, current_user)
                else:
                    return None
            if not (already_shown or force) or (asked_id != current_points_id):
                question = timdb.questions.get_asked_question(asked_id)[0]
                tempdb.pointsshown.add_user_info(lecture_id, asked_id, current_user)
                answer = timdb.lecture_answers.get_user_answer_to_question(asked_id, current_user)
                if answer:
                    userpoints = answer[0]['points']
                    answer = answer[0]['answer']
                    return {"result": True, 'askedId': asked_id, "questionjson": question["json"], "answer": answer,
                            "userpoints": userpoints,
                            "expl": question["expl"], "points": question["points"]}
        return None


def check_if_lecture_is_ending(current_user, lecture: Lecture):
    """Checks if the lecture is about to end. 1 -> ends in 1 min. 5 -> ends in 5 min. 100 -> goes on atleast for 5 mins.

    :param current_user: The current user id.
    :param lecture: The lecture object.
    :return:

    """
    lecture_ending = 100
    if lecture.lecturer == current_user:
        time_now = datetime.now(timezone.utc)
        ending_time = lecture.end_time
        time_left = ending_time - time_now
        if time_left.total_seconds() <= 60:
            return 1
        elif time_left.total_seconds() <= 60 * 5:
            return 5
    return lecture_ending


@lecture_routes.route('/sendMessage', methods=['POST'])
def send_message():
    """Route to add message to database."""
    timdb = get_timdb()
    new_message = request.args.get("message")
    lecture_id = int(request.args.get("lecture_id"))

    new_timestamp = datetime.now(timezone.utc)  # was timezone.utc)
    msg_id = timdb.messages.add_message(get_current_user_id(), lecture_id, new_message, new_timestamp, True)
    return json_response({'id': msg_id, 'time': new_timestamp})


def get_lecture_session_data():
    for k in ('use_wall', 'use_questions'):
        if session.get(k) is None:
            session[k] = True
    return {
        'useWall': session['use_wall'],
        'useQuestions': session['use_questions'],
    }


@lecture_routes.route('/checkLecture', methods=['GET'])
def check_lecture():
    """Route to check if the current user is in some lecture in specific document."""
    timdb = get_timdb()
    tempdb = get_tempdb()
    current_user = get_current_user_id()
    lectures = timdb.lectures.check_if_in_any_lecture(current_user)
    lecture = lectures[0] if lectures else None

    lecturers = []
    students = []
    if lecture:
        if check_if_lecture_is_running(lecture):
            if lecture.lecturer == current_user:
                is_lecturer = True
                lecturers, students = get_lecture_users(timdb, tempdb, lecture.lecture_id)
            else:
                is_lecturer = False

            return json_response({
                "lecture": lecture,
                "isInLecture": True,
                "isLecturer": is_lecturer,
                "lecturers": lecturers,
                "students": students,
                **get_lecture_session_data(),
            })
        else:
            leave_lecture_function(lecture.lecture_id)
            timdb.lectures.delete_users_from_lecture(lecture.lecture_id)
            clean_dictionaries_by_lecture(lecture.lecture_id)
    doc_id = request.args.get('doc_id')
    if doc_id is not None:
        return get_running_lectures(int(doc_id))
    else:
        return json_response("")


@lecture_routes.route("/startFutureLecture", methods=['POST'])
def start_future_lecture():
    if not request.args.get('lecture_code') or not request.args.get("doc_id"):
        abort(400)

    timdb = get_timdb()
    tempdb = get_tempdb()
    lecture_code = request.args.get('lecture_code')
    doc_id = int(request.args.get("doc_id"))
    d = get_doc_or_abort(doc_id)
    verify_ownership(d)
    lecture = timdb.lectures.get_lecture_by_code(lecture_code, doc_id)
    time_now = datetime.now(timezone.utc)
    lecture.start_time = time_now
    db.session.commit()
    timdb.lectures.join_lecture(lecture.lecture_id, get_current_user_id(), True)
    students, lecturers = get_lecture_users(timdb, tempdb, lecture.lecture_id)
    return json_response({
        "lecture": lecture,
        "isLecturer": True,
        "isInLecture": True,
        "students": students,
        "lecturers": lecturers,
        **get_lecture_session_data(),
    })


@lecture_routes.route('/getAllLecturesFromDocument', methods=['GET'])
def get_all_lectures():
    if not request.args.get('doc_id'):
        abort(400)

    doc_id = int(request.args.get('doc_id'))
    timdb = get_timdb()

    lectures = timdb.lectures.get_all_lectures_from_document(doc_id)
    time_now = datetime.now(timezone.utc)
    current_lectures = []
    past_lectures = []
    future_lectures = []
    for lecture in lectures:
        if lecture.start_time <= time_now < lecture.end_time:
            current_lectures.append(lecture)
        elif lecture.end_time <= time_now:
            past_lectures.append(lecture)
        else:
            future_lectures.append(lecture)

    return json_response(
        {"currentLectures": current_lectures, "futureLectures": future_lectures, "pastLectures": past_lectures})


@lecture_routes.route('/showLectureInfo/<int:lecture_id>', methods=['GET'])
def show_lecture_info(lecture_id):
    timdb = get_timdb()
    lecture = timdb.lectures.get_lecture(lecture_id)
    if not lecture:
        abort(400, 'Lecture not found')

    doc = DocEntry.find_by_id(lecture.doc_id)
    lectures = timdb.lectures.check_if_in_any_lecture(get_current_user_id())
    settings = get_user_settings()
    return render_template("lectureInfo.html",
                           item=doc,
                           lectureId=lecture_id,
                           lectureCode=lecture.lecture_code,
                           lectureStartTime=lecture.start_time,
                           lectureEndTime=lecture.end_time,
                           in_lecture=len(lectures) > 0,
                           settings=settings,
                           translations=doc.translations)


@lecture_routes.route('/showLectureInfoGivenName/', methods=['GET'])
def show_lecture_info_given_name():
    timdb = get_timdb()
    if 'lecture_id' in request.args:
        lecture = timdb.lectures.get_lecture(int(request.args.get('lecture_id')))
    else:
        lecture = timdb.lectures.get_lecture_by_name(request.args.get('lecture_code'), int(request.args.get('doc_id')))
    if not lecture:
        abort(400)

    current_user = get_current_user_id()

    return json_response(lecture.to_json(show_password=lecture.lecturer == current_user))


@lecture_routes.route('/lectureNeedsPassword/', methods=['GET'])
def lecture_needs_password():
    timdb = get_timdb()
    if 'lecture_id' in request.args:
        lecture = timdb.lectures.get_lecture(int(request.args.get('lecture_id')))
    else:
        lecture = timdb.lectures.get_lecture_by_name(request.args.get('lecture_code'), int(request.args.get('doc_id')))
    if not lecture:
        abort(400)
    return json_response(lecture.password != '')


def get_lecture_users(timdb, tempdb, lecture_id):
    lecture = timdb.lectures.get_lecture(lecture_id)
    lecturers = []
    students = []

    activity = tempdb.useractivity.get_all_user_activity(lecture_id)

    for user in activity:
        user_id = user.user_id
        active = user.active
        person = {
            "name": timdb.users.get_user(user_id).get("name"),
            "active": active,
            "user_id": user_id
        }
        if lecture.lecturer == user_id:
            lecturers.append(person)
        else:
            students.append(person)

    return lecturers, students


def check_if_lecture_is_running(lecture: Lecture):
    time_now = datetime.now(timezone.utc)
    return lecture.start_time <= time_now < lecture.end_time


def get_running_lectures(doc_id=None):
    """Gets all running and future lectures.

    :param doc_id: The document id for which to get lectures.

    """
    timdb = get_timdb()
    time_now = datetime.now(timezone.utc)
    list_of_lectures = []
    is_lecturer = False
    if doc_id:
        list_of_lectures = timdb.lectures.get_document_lectures(doc_id, time_now)
        d = get_doc_or_abort(doc_id)
        is_lecturer = bool(has_ownership(d))
    current_lectures = []
    future_lectures = []
    for lecture in list_of_lectures:
        if lecture.start_time <= time_now < lecture.end_time:
            current_lectures.append(lecture)
        else:
            future_lectures.append(lecture)
    return json_response(
        {
            "isLecturer": is_lecturer,
            "lectures": current_lectures,
            "futureLectures": future_lectures,
        })


@lecture_routes.route('/createLecture', methods=['POST'])
def create_lecture():
    doc_id, start_time, end_time, lecture_code = verify_json_params('doc_id', 'start_time', 'end_time', 'lecture_code')
    start_time = dateutil.parser.parse(start_time)
    end_time = dateutil.parser.parse(end_time)
    lecture_id, password, options = verify_json_params('lecture_id', 'password', 'options', require=False)
    d = get_doc_or_abort(doc_id)
    verify_ownership(d)
    timdb = get_timdb()

    if not options:
        options = {}

    if not password:
        password = ""
    current_user = get_current_user_id()
    if not timdb.lectures.check_if_correct_name(doc_id, lecture_code, lecture_id):
        abort(400, "Can't create two or more lectures with the same name to the same document.")

    options = json.dumps(options)
    if lecture_id is None:
        lecture_id = timdb.lectures.create_lecture(doc_id, current_user, start_time, end_time, lecture_code, password,
                                                   options, True)
    else:
        timdb.lectures.update_lecture(lecture_id, doc_id, current_user, start_time, end_time, lecture_code, password,
                                      options)

    current_time = datetime.now(timezone.utc)

    if start_time <= current_time <= end_time:
        timdb.lectures.join_lecture(lecture_id, current_user, True)
    return json_response({"lectureId": lecture_id})


@lecture_routes.route('/endLecture', methods=['POST'])
def end_lecture():
    lecture = get_lecture_from_request()
    timdb = get_timdb()
    timdb.lectures.delete_users_from_lecture(lecture.lecture_id)

    now = datetime.now(timezone.utc)
    timdb.lectures.set_end_for_lecture(lecture.lecture_id, now)

    clean_dictionaries_by_lecture(lecture.lecture_id)

    return get_running_lectures(lecture.doc_id)


def clean_dictionaries_by_lecture(lecture_id):
    """Cleans data from lecture that isn't running anymore.

    :param lecture_id: The lecture id.

    """
    tempdb = get_tempdb()
    tempdb.runningquestions.delete_lectures_running_questions(lecture_id)
    tempdb.usersshown.delete_all_from_lecture(lecture_id)
    tempdb.usersextended.delete_all_from_lecture(lecture_id)
    tempdb.useractivity.delete_lecture_activity(lecture_id)
    tempdb.newanswers.delete_lecture_answers(lecture_id)
    tempdb.showpoints.stop_showing_points(lecture_id)
    tempdb.pointsshown.delete_all_from_lecture(lecture_id)


@lecture_routes.route('/extendLecture', methods=['POST'])
def extend_lecture():
    new_end_time = request.args.get("new_end_time")
    if not new_end_time:
        abort(400)
    lecture = get_lecture_from_request()
    timdb = get_timdb()
    timdb.lectures.extend_lecture(lecture.lecture_id, new_end_time)
    return ok_response()


@lecture_routes.route('/deleteLecture', methods=['POST'])
def delete_lecture():
    lecture = get_lecture_from_request()

    Message.query.filter_by(lecture_id=lecture.lecture_id).delete()
    LectureUsers.query.filter_by(lecture_id=lecture.lecture_id).delete()
    LectureAnswer.query.filter_by(lecture_id=lecture.lecture_id).delete()
    AskedQuestion.query.filter_by(lecture_id=lecture.lecture_id).delete()
    db.session.delete(lecture)
    db.session.commit()

    clean_dictionaries_by_lecture(lecture.lecture_id)

    return get_running_lectures(lecture.doc_id)


def get_lecture_from_request(check_access=True) -> Lecture:
    if not request.args.get("lecture_id"):
        abort(400)
    lecture_id = int(request.args.get("lecture_id"))
    lecture = Lecture.find_by_id(lecture_id)
    if not lecture:
        abort(404)
    if check_access:
        d = get_doc_or_abort(lecture.doc_id)
        verify_ownership(d)
    return lecture


@lecture_routes.route('/joinLecture', methods=['POST'])
def join_lecture():
    """Route to join lecture.

    Checks that the given password is correct.

    """
    if not request.args.get("doc_id") or not request.args.get("lecture_code"):
        abort(400, "Missing parameters")
    timdb = get_timdb()
    tempdb = get_tempdb()
    doc_id = int(request.args.get("doc_id"))
    lecture_code = request.args.get("lecture_code")
    password_quess = request.args.get("password_quess")
    lecture = timdb.lectures.get_lecture_by_code(lecture_code, doc_id)
    lecture_id = lecture.lecture_id
    current_user = get_current_user_id()

    lecture_ended = not check_if_lecture_is_running(lecture)

    # TODO Allow lecturer always join, even if the lecture is full
    lecture_full = lecture.is_full

    correct_password = True
    if lecture.password != password_quess:
        correct_password = False

    joined = False
    lectures = timdb.lectures.check_if_in_any_lecture(current_user)
    if not lecture_ended and not lecture_full and correct_password:
        if not logged_in():
            anon_user = log_in_as_anonymous(session)
            current_user = anon_user.id
        if lectures:
            leave_lecture_function(lectures[0].lecture_id)
        timdb.lectures.join_lecture(lecture_id, current_user, True)
        joined = True

        time_now = str(datetime.now(timezone.utc).strftime("%H:%M:%S"))
        tempdb.useractivity.update_or_add_activity(lecture_id, current_user, time_now)

        session['in_lecture'] = [lecture_id]

    lecturers = []
    students = []
    if lecture.lecturer == current_user:
        is_lecturer = True
        lecturers, students = get_lecture_users(timdb, tempdb, lecture_id)
    else:
        is_lecturer = False
    return json_response(
        {
            "correctPassword": correct_password,
            "isInLecture": joined or in_lecture,
            "isLecturer": is_lecturer,
            "lecture": lecture,
            "lecturers": lecturers,
            "students": students,
            **get_lecture_session_data(),
        })


@lecture_routes.route('/leaveLecture', methods=['POST'])
def leave_lecture():
    lecture_id = get_option(request, 'lecture_id', None, cast=int)
    if not lecture_id:
        abort(400)
    leave_lecture_function(lecture_id)
    return ok_response()


def leave_lecture_function(lecture_id):
    timdb = get_timdb()
    current_user = get_current_user_id()
    if 'in_lecture' in session:
        lecture_list = session['in_lecture']
        if lecture_id in lecture_list:
            lecture_list.remove(lecture_id)
        session['in_lecture'] = lecture_list
    timdb.lectures.leave_lecture(lecture_id, current_user, True)

    # if (current_user, lecture_id) in __user_activity:
    #    del __user_activity[current_user, lecture_id]


@lecture_routes.route("/extendQuestion", methods=['POST'])
def extend_question():
    asked_id = int(request.args.get('asked_id'))
    extend = int(request.args.get('extend'))

    tempdb = get_tempdb()
    tempdb.runningquestions.extend_question(asked_id, extend * 1000)

    return json_response('Extended')


@lecture_routes.route("/askQuestion", methods=['POST'])
def ask_question():
    if not request.args.get('doc_id') or not \
            (request.args.get('question_id') or request.args.get('asked_id') or request.args.get('par_id')) or not \
            request.args.get('lecture_id'):
        abort(400, "Bad request")
    doc_id = int(request.args.get('doc_id'))
    lecture_id = int(request.args.get('lecture_id'))
    question_id = None
    asked_id = None
    par_id = None
    if 'question_id' in request.args:
        question_id = int(request.args.get('question_id'))
    elif 'asked_id' in request.args:
        asked_id = int(request.args.get('asked_id'))
    else:
        par_id = request.args.get('par_id')

    d = get_doc_or_abort(doc_id)
    verify_ownership(d)

    if lecture_id < 0:
        abort(400, "Not valid lecture id")

    timdb = get_timdb()

    if question_id or par_id:
        if question_id:
            question = timdb.questions.get_question(question_id)[0]  # Old version???
            question_json_str = question.get("questionjson")
            markup = json.loads(question_json_str)
            expl = question.get("expl")
            points = question.get("points")
        else:
            markup = get_question_data_from_document(doc_id, par_id)
            delete_key(markup, "qst")
            # question_json_str = json.dumps(markup.get('json'))
            question_json_str = json.dumps(markup)
            expl = json.dumps(markup.get('expl', ''))
            points = markup.get('points', '')

        if not points:
            points = "0:0"
        question_hash = hashfunc(question_json_str)
        asked_hash = timdb.questions.get_asked_json_by_hash(question_hash)
        if asked_hash:
            asked_json_id = asked_hash[0].get("asked_json_id")
        else:
            asked_json_id = timdb.questions.add_asked_json(question_json_str, question_hash)

        asked_time = datetime.now(timezone.utc)
        asked_id = timdb.questions.add_asked_questions(lecture_id, doc_id, None, asked_time, points,
                                                       asked_json_id, expl)
    elif asked_id:
        question = timdb.questions.get_asked_question(asked_id)[0]
        asked_json = timdb.questions.get_asked_json_by_id(question["asked_json_id"])[0]
        asked_json_id = asked_json["asked_json_id"]
        question_json_str = asked_json["json"]  # actually now markup
        markup = json.loads(question_json_str)

    if "json" not in markup:  # compatibility for old version
        markup = {"json": markup}

    question_timelimit = 0
    try:
        tl = markup.get("json").get("timeLimit", "0")
        if not tl:
            tl = "0"
        question_timelimit = int(tl)
    except:
        pass

    ask_time = int(time.time() * 1000)
    end_time = ask_time + question_timelimit * 1000
    thread_to_stop_question = threading.Thread(target=stop_question_from_running,
                                               args=(lecture_id, asked_id, question_timelimit, end_time))

    thread_to_stop_question.start()

    tempdb = get_tempdb()
    delete_question_temp_data(asked_id, lecture_id, tempdb)

    tempdb.runningquestions.add_running_question(lecture_id, asked_id, ask_time, end_time)

    return json_response(asked_id)


def delete_question_temp_data(asked_id, lecture_id, tempdb):
    tempdb.runningquestions.delete_lectures_running_questions(lecture_id)
    tempdb.usersshown.delete_all_from_question(asked_id)
    tempdb.usersextended.delete_all_from_question(asked_id)
    tempdb.newanswers.delete_question_answers(asked_id)
    tempdb.showpoints.stop_showing_points(lecture_id)
    tempdb.pointsshown.delete_all_from_lecture(lecture_id)
    tempdb.pointsclosed.delete_all_from_lecture(lecture_id)


@lecture_routes.route('/showAnswerPoints', methods=['POST'])
def show_points():
    if 'asked_id' not in request.args or 'lecture_id' not in request.args:
        abort(400)
    asked_id = int(request.args.get('asked_id'))
    lecture_id = int(request.args.get('lecture_id'))

    tempdb = get_tempdb()
    tempdb.showpoints.stop_showing_points(lecture_id)
    tempdb.showpoints.add_show_points(lecture_id, asked_id)

    current_question_id = None
    current_points_id = None
    if 'current_question_id' in request.args:
        current_question_id = int(request.args.get('current_question_id'))
    if 'current_points_id' in request.args:
        current_points_id = int(request.args.get('current_points_id'))
    new_question = get_new_question(lecture_id, current_question_id, current_points_id)
    if new_question is not None:
        resp = {}
        resp.update(new_question)
        return json_response(resp)

    return json_response("")


@lecture_routes.route('/updatePoints/', methods=['POST'])
def update_question_points():
    """Route to get add question to database."""
    if 'asked_id' not in request.args or 'points' not in request.args:
        abort(400)
    asked_id = int(request.args.get('asked_id'))
    points = request.args.get('points')
    expl = request.args.get('expl')
    timdb = get_timdb()
    asked_question = timdb.questions.get_asked_question(asked_id)[0]
    lecture_id = int(asked_question['lecture_id'])
    if not check_if_is_lecturer(lecture_id):
        abort(400)
    timdb.questions.update_asked_question_points(asked_id, points, expl)
    points_table = create_points_table(points)
    question_answers = timdb.lecture_answers.get_answers_to_question(asked_id)
    for answer in question_answers:
        user_points = calculate_points(answer['answer'], points_table)
        timdb.lecture_answers.update_answer_points(answer['answer_id'], user_points)
    return ok_response()


def stop_question_from_running(lecture_id, asked_id, question_timelimit, end_time):
    with app.app_context():
        if question_timelimit == 0:
            return
        tempdb = get_tempdb()
        # Adding extra time to limit so when people gets question a bit later than others they still get to answer
        extra_time = 3
        end_time += extra_time * 1000
        while int(time.time() * 1000) < end_time:  # TODO: check carefully if any sense
            time.sleep(1)
            stopped = True
            question = tempdb.runningquestions.get_running_question_by_id(asked_id)
            if question:
                end_time = extra_time * 1000 + question.end_time
                stopped = False

            if stopped:
                tempdb.newanswers.delete_question_answers(asked_id)
                return

        tempdb.runningquestions.delete_running_question(asked_id)
        tempdb.usersshown.delete_all_from_question(asked_id)
        tempdb.usersextended.delete_all_from_question(asked_id)
        tempdb.usersanswered.delete_all_from_lecture(asked_id)
        tempdb.newanswers.delete_question_answers(asked_id)


@lecture_routes.route("/getQuestionByParId", methods=['GET'])
def get_question_by_par_id():
    if not request.args.get("par_id") or not request.args.get("doc_id"):
        abort(400)
    doc_id = int(request.args.get('doc_id'))
    par_id = request.args.get('par_id')
    edit = request.args.get('edit', False)
    d = get_doc_or_abort(doc_id)
    verify_ownership(d)
    # question_json, points, expl, markup = get_question_data_from_document(doc_id, par_id)
    # return json_response({"points": points, "questionjson": question_json, "expl": expl, "markup": markup})
    markup = get_question_data_from_document(doc_id, par_id, edit)
    return json_response({"markup": markup})


@lecture_routes.route("/getAskedQuestionById", methods=['GET'])
def get_asked_question_by_id():
    if not request.args.get("asked_id"):
        abort(400)
    # doc_id = int(request.args.get('doc_id'))
    asked_id = int(request.args.get('asked_id'))
    timdb = get_timdb()
    question = timdb.questions.get_asked_question(asked_id)[0]
    lecture_id = question['lecture_id']
    if not check_if_is_lecturer(lecture_id):
        abort(400)
    return json_response(question)


def check_if_is_lecturer(lecture_id):
    timdb = get_timdb()
    current_user = get_current_user_id()
    return timdb.lectures.get_lecture(lecture_id).lecturer == current_user


@lecture_routes.route("/stopQuestion", methods=['POST'])
def stop_question():
    """Route to stop question from running."""
    if not request.args.get("asked_id") or not request.args.get("lecture_id"):
        abort(400)
    asked_id = int(request.args.get('asked_id'))
    lecture_id = int(request.args.get('lecture_id'))
    timdb = get_timdb()
    tempdb = get_tempdb()
    current_user = get_current_user_id()
    lecture = timdb.lectures.get_lecture(lecture_id)
    if lecture:
        if lecture.lecturer != current_user:
            abort(400, "You cannot stop questions on someone elses lecture.")
        tempdb.runningquestions.delete_running_question(asked_id)
        tempdb.usersshown.delete_all_from_question(asked_id)
        tempdb.usersanswered.delete_all_from_question(asked_id)
    return ok_response()


@lecture_routes.route("/getLectureAnswers", methods=['GET'])
def get_lecture_answers():
    """Changing this to long poll requires removing threads."""
    if not request.args.get('asked_id'):
        abort(400, "Bad request")

    asked_id = int(request.args.get('asked_id'))

    rq = Runningquestion.query.filter_by(asked_id=asked_id).one()
    lecture = Lecture.query.get(rq.lecture_id)
    verify_ownership(lecture.doc_id)
    tempdb = get_tempdb()

    step = 0
    user_ids = []
    while step <= 10:
        step = 11
        question = tempdb.runningquestions.get_running_question_by_id(asked_id)
        if not question:
            return json_response({"noAnswer": True})
        user_ids = tempdb.newanswers.get_new_answers(asked_id)
        if user_ids:
            break

        step += 1
        # time.sleep(1)

    timdb = get_timdb()
    lecture_answers = []

    for user_id in user_ids:
        lecture_answers.append(timdb.lecture_answers.get_user_answer_to_question(asked_id, user_id)[0])

    latest_answer = datetime.now(timezone.utc)

    return json_response({"answers": lecture_answers, "askedId": asked_id, "latestAnswer": latest_answer})


@lecture_routes.route("/answerToQuestion", methods=['PUT'])
def answer_to_question():
    if not request.args.get("asked_id") or not request.args.get('input') or not request.args.get('lecture_id'):
        abort(400, "Bad request")

    timdb = get_timdb()
    tempdb = get_tempdb()

    asked_id = int(request.args.get("asked_id"))
    req_input = json.loads(request.args.get("input"))
    answer = req_input['answers']
    whole_answer = answer
    lecture_id = int(request.args.get("lecture_id"))
    current_user = get_current_user_id()

    lecture_answer = timdb.lecture_answers.get_user_answer_to_question(asked_id, current_user)

    question = tempdb.runningquestions.get_running_question_by_id(asked_id)
    already_answered = tempdb.usersanswered.has_user_info(asked_id, current_user)
    if not question:
        return json_response({"questionLate": "The question has already finished. Your answer was not saved."})
    if already_answered:
        return json_response({"alreadyAnswered": "You have already answered to question. Your first answer is saved."})

    tempdb.usersanswered.add_user_info(lecture_id, asked_id, current_user)

    if (not lecture_answer) or (lecture_answer and answer != lecture_answer[0]["answer"]):
        time_now = datetime.now(timezone.utc)
        question_points = timdb.questions.get_asked_question(asked_id)[0].get("points")
        points_table = create_points_table(question_points)
        points = calculate_points_from_json_answer(answer, points_table)
        if lecture_answer and current_user != 0:
            timdb.lecture_answers.update_answer(lecture_answer[0]["answer_id"], current_user, asked_id,
                                                lecture_id, json.dumps(whole_answer), time_now, points)
        else:
            timdb.lecture_answers.add_answer(current_user, asked_id, lecture_id, json.dumps(whole_answer), time_now,
                                             points)
        tempdb.newanswers.user_answered(lecture_id, asked_id, current_user)

    return json_response("")


@lecture_routes.route("/closePoints", methods=['PUT'])
def close_points():
    if not request.args.get("asked_id") or not request.args.get('lecture_id'):
        abort(400, "Bad request")

    tempdb = get_tempdb()

    asked_id = int(request.args.get("asked_id"))
    lecture_id = int(request.args.get("lecture_id"))
    current_user = get_current_user_id()

    points = tempdb.showpoints.get_currently_shown_points(lecture_id)
    if points:
        tempdb.pointsclosed.add_user_info(lecture_id, asked_id, current_user)

    return ok_response()


def user_in_lecture():
    timdb = get_timdb()
    current_user = get_current_user_id()
    lectures = timdb.lectures.check_if_in_any_lecture(current_user)
    in_lecture = False
    if lectures:
        lecture = lectures[0]
        in_lecture = lecture and check_if_lecture_is_running(lecture)
    return in_lecture


def get_tempdb():
    return TempDb(session=db.session)
