"""
The module handles the main logic related to annotations. This includes adding, modifiying and deleting annotations
as well as adding comments to the annotations. The module also retrieves the annotations to the document.

:authors: Joonas Lattu, Petteri Palojärvi
:copyright: 2016 Timber project members
:version: 1.0.0

"""

from typing import Dict
from flask import Blueprint
from .common import *
from timdb.annotations import Annotations

annotations = Blueprint('annotations',
                        __name__,
                        url_prefix='')


# TODO connect the routes in this file to the ui.
@annotations.route("/add_annotation", methods=['POST'])
def add_annotation() -> Dict:
    """Creates a new annotation to the database.

    Required key(s):
        - velp: velp ID
        - visible_to: visibility group (1-4)
        - doc_id: document ID
        - coord: start and end coordinates of the annotation.

    :return: Dictionary oontaining annotation id and annotator name.
    """
    json_data = request.get_json()
    print(json_data)
    timdb = getTimDb()

    # first get the non-optional arguments and abort if there is missing data.
    try:
        velp_id = json_data['velp']
        visible_to = timdb.annotations.AnnotationVisibility(json_data['visible_to'])
        document_id = json_data['doc_id']
        coordinates = json_data['coord']
        start = coordinates['start']
        end = coordinates['end']

    except KeyError as e:  # one of the json_data['foo'] fails
        return abort(400, "Missing data: " + e.args[0])
    except TypeError as e:  # one of the element paths is not a list of integers
        return abort(400, "Malformed element path. " + e.args[0])
    except ValueError as e:  # visible_to could not be casted to the enum used.
        return abort(400, e.args[0])

    # .get() returns None if there is no data instead of throwing.
    offset_start = start.get('offset')
    depth_start = start.get('depth')
    node_start = start.get('node')

    offset_end = end.get('offset')
    depth_end = end.get('depth')
    node_end = end.get('node')

    element_path_start = start.get('el_path')
    if element_path_start is not None:
        if type(element_path_start) is not list or any(type(i) is not int for i in element_path_start):
            return abort(400, "Malformed element path. " + str(element_path_start))
        element_path_start = str(element_path_start)

    element_path_end = end.get('el_path')
    if element_path_end is not None:
        if type(element_path_end) is not list or any(type(i) is not int for i in element_path_end):
            return abort(400, "Malformed element path. " + str(element_path_end))
        element_path_end = str(element_path_end)

    points = json_data.get('points')
    icon_id = json_data.get('icon_id')
    answer_id = json_data.get('answer_id')

    try:
        paragraph_id_start = start['par_id']
        hash_start = start['t']
        paragraph_id_end = end['par_id']
        hash_end = end['t']
    except KeyError as e:
        return abort(400, "Missing data: " + e.args[0])
    verifyLoggedIn()
    annotator_id = getCurrentUserId()
    velp_version_id = timdb.velps.get_latest_velp_version(velp_id)["id"]

    new_id = timdb.annotations.create_annotation(velp_version_id, visible_to, points, annotator_id, document_id,
                                                 paragraph_id_start, paragraph_id_end, offset_start, node_start,
                                                 depth_start, offset_end, node_end, depth_end, hash_start, hash_end,
                                                 element_path_start, element_path_end, None, icon_id, answer_id)

    return jsonResponse({"id": new_id, "annotator_name": timdb.users.get_user(annotator_id)['name']})


@annotations.route("/update_annotation", methods=['POST'])
def update_annotation():
    """Updates the visibility and/or points of the annotation.

    Required key(s):
        - annotation_id: annotation ID.

    Optional key(s):
        - visible_to: visibility group number (1-4)
        - points: number of points
        - doc_id: document ID.

    :return: okJsonResponse()
    """
    verifyLoggedIn()
    user_id = getCurrentUserId()
    json_data = request.get_json()
    try:
        annotation_id = json_data['annotation_id']
    except KeyError as e:
        return abort(400, "Missing data: " + e.args[0])
    visible_to = json_data.get('visible_to')
    points = json_data.get('points')
    doc_id = json_data.get('doc_id')
    timdb = getTimDb()
    # Get values from the database to fill in unchanged new values.
    new_values = timdb.annotations.get_annotation(annotation_id)
    if not new_values:
        return abort(404, "No such annotation.")
    new_values = new_values[0]
    # Todo panic if there is more than one item in the list.
    if not new_values['annotator_id'] == user_id:
        return abort(403, "You are not the annotator.")
    if visible_to:
        try:
            visible_to = Annotations.AnnotationVisibility(visible_to)
        except ValueError as e:
            return abort(400, "Visibility should be 1, 2, 3 or 4.")
        new_values['visible_to'] = visible_to
    if timdb.users.has_teacher_access(user_id, doc_id):
        new_values['points'] = points
    else:
        if points is None:
            new_values['points'] = points
        else:
            new_values['points'] = None
    timdb.annotations.update_annotation(new_values['id'], new_values['velp_version_id'],
                                        new_values['visible_to'], new_values['points'], new_values['icon_id'])
    return okJsonResponse()


@annotations.route("/invalidate_annotation", methods=['POST'])
def invalidate_annotation():
    """Invalidates annotation by setting its valid from to current moment.

    Required key(s):
        - annotation_id: annotation ID

    :return: okJsonResponse()
    """
    json_data = request.get_json()
    try:
        annotation_id = json_data['annotation_id']
    except KeyError as e:
        return abort(400, "Missing data: " + e.args[0])
    timdb = getTimDb()
    annotation = timdb.annotations.get_annotation(annotation_id)
    if not annotation:
        return abort(404, "No such annotation.")
    annotation = annotation[0]
    verifyLoggedIn()
    user_id = getCurrentUserId()
    if not annotation['annotator_id'] == user_id:
        return abort(403, "You are not the annotator.")
    # TODO: Add option to choose when annotation gets invalidated
    timdb.annotations.invalidate_annotation(annotation_id)

    return okJsonResponse()


@annotations.route("/add_annotation_comment", methods=['POST'])
def add_comment() -> Dict:
    """Adds new comment to the annotation.

    Required key(s):
        - annotation_id: annotation ID
        - content: content of the comment.

    :return: Dictionary of information about user who added the comment
    """
    json_data = request.get_json()
    try:
        annotation_id = json_data['annotation_id']
        content = json_data['content']
    except KeyError as e:
        return abort(400, "Missing data: " + e.args[0])
    # Todo maybe check that content isn't an empty string
    timdb = getTimDb()
    verifyLoggedIn()
    commenter_id = getCurrentUserId()
    timdb.annotations.add_comment(annotation_id, commenter_id, content)
    # TODO notice with email to annotator if commenter is not itself
    return jsonResponse(timdb.users.get_user(commenter_id))


@annotations.route("/<int:doc_id>/get_annotations", methods=['GET'])
def get_annotations(doc_id: int):
    """Returns all annotations with comments user can see, e.g. has access to them in a document.

    :param doc_id: ID of the document
    :return: List of dictionaries containing annotations with comments
    """
    timdb = getTimDb()
    user_id = getCurrentUserId()
    if not timdb.documents.exists(doc_id):
        return abort(404, "No such document.")
    if not timdb.users.has_view_access(user_id, doc_id):
        return abort(403, "View access required.")
    user_has_see_answers = timdb.users.has_seeanswers_access(user_id, doc_id)
    user_has_teacher = timdb.users.has_teacher_access(user_id, doc_id)
    user_has_owner = timdb.users.user_is_owner(user_id, doc_id)

    results = timdb.annotations.get_annotations_with_comments_in_document(getCurrentUserId(), user_has_see_answers,
                                                                          user_has_teacher, user_has_owner, doc_id)
    response = jsonResponse(results)
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
    return response

