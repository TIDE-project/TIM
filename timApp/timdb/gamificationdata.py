# Collection of gamification functions
from timdb.models.docentry import DocEntry
import yaml
import json
from flask import request
import pluginControl
from routes.dbaccess import get_timdb
from routes import common


def gamify(initial_data):

    # Convert initial data to JSON format
    initial_json = convert_to_json(initial_data)

    # Find document IDs from json, and place them in their appropriate arrays(lectures and demos separately)
    lecture_table, demo_table = get_doc_ids(initial_json)

    # Insert document, IDs, paths, and points in a dictionary
    place_in_dict(lecture_table, demo_table)


def convert_to_json(md_data):
    """Converts the YAML paragraph in gamification document to JSON
    :param md_data = the data read from paragraph in YAML
    :returns: same data in JSON
    """
    temp = yaml.load(md_data[3:len(md_data) - 3])
    return json.loads(json.dumps(temp))


def get_doc_ids(json_to_check):
    """Parses json to find names of lecture and demo documents
    :param json_to_check = Checked documents in JSON
    :returns:
    """
    if json_to_check is None:
        raise GamificationException('JSON is None')

    lecture_paths = json_to_check['lectures']
    demo_paths = json_to_check['demos']

    lectures = []
    for path in lecture_paths:
        lecture = DocEntry.find_by_path(path['path'])
        if lecture is not None:
            temp_dict1 = dict()
            temp_dict1['id'] = lecture.id
            temp_dict1['name'] = lecture.get_short_name()
            temp_dict1['url'] = request.url_root+'view/' + lecture.get_path()
            lectures.append(temp_dict1)

    demos = []
    for path in demo_paths:
        demo = DocEntry.find_by_path(path['path'])
        if demo is not None:
            temp_dict2 = dict()
            temp_dict2['id'] = demo.id
            temp_dict2['name'] = demo.get_short_name()
            temp_dict2['url'] = request.url_root+'view/' + demo.get_path()
            temp_dict2['points'] = get_points_for_doc(demo)
            demos.append(temp_dict2)

    return lectures, demos


def place_in_dict(l_table, d_table):
    """
    :param l_table Array of lecture IDs
    :param d_table Array of demo IDs
    :returns:
    """
    document_dict = {'lectures': [], 'demos': []}

    temp1 = document_dict['lectures']
    for i in range(len(l_table)):
        temp1.append(l_table[i])

    temp2 = document_dict['demos']
    for j in range(len(d_table)):
        temp2.append(d_table[j])

    print(temp1, temp2)
    return


def get_points_for_doc(d):
    document = d.document
    timdb = get_timdb()
    user_points = 0
    task_id_list = (pluginControl.find_task_ids(document.get_paragraphs()))
    users_task_info = timdb.answers.get_users_for_tasks(task_id_list[0], [common.get_current_user_id()])

    for entrys in users_task_info:
        if users_task_info is not None:
            user_points += (users_task_info[0]['total_points'])

    return user_points


class GamificationException(Exception):
    """The exception that is thrown when an error occurs during a gamification check."""
    pass
