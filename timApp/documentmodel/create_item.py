# -*- coding: utf-8 -*-

from typing import List, Optional

from timApp.timdb.docinfo import DocInfo
from timApp.timdb.models.docentry import DocEntry, get_documents
from timApp.timdb.models.translation import Translation
from timApp.timdb.tim_models import db
from timApp.validation import validate_item_and_create
from timApp.timdb.dbutils import copy_default_rights
from timApp.timdb.blocktypes import from_str, blocktypes
from timApp.dbaccess import get_timdb
from timApp.accesshelper import grant_access_to_session_users
from timApp.timdb.bookmarks import Bookmarks
from timApp.sessioninfo import get_current_user_object, get_current_user_group
from timApp.tim_app import app
from timApp.timdb.models.folder import Folder
from timApp.responsehelper import json_response
from timApp.timdb.userutils import DOC_DEFAULT_RIGHT_NAME, FOLDER_DEFAULT_RIGHT_NAME
from timApp.accesshelper import get_viewable_blocks_or_none_if_admin

FORCED_TEMPLATE_NAME = 'force'

special_names = ['Templates', 'Printing']


def path_and_shortname(item_path: str) -> [str, str]:
    """
    Divide name to path and shortname
    :param item_path: name to divide
    :return: path and shortname
    """
    ind = item_path.rfind('/')
    if ind < 0:
        return '', item_path
    return item_path[0:ind + 1], item_path[ind + 1:]


def check_for_special_name(item_path: str) -> str:
    """
    Check if shortname is one of the special names and if it is, change the typing correctly
    :param item_path: name to check
    :return: names case changed correctly if special name
    """
    ipath, sname = path_and_shortname(item_path)

    for sn in special_names:
        if sn.upper() == sname.upper():
            return ipath + sn
            break
    return item_path


def create_item(item_path, item_type_str, item_title, create_function, owner_group_id):
    item_path = check_for_special_name(item_path.strip('/'))

    validate_item_and_create(item_path, item_type_str, owner_group_id)

    item = create_function(item_path, owner_group_id, item_title)
    timdb = get_timdb()
    grant_access_to_session_users(timdb, item.id)
    item_type = from_str(item_type_str)
    if item_type == blocktypes.DOCUMENT:
        bms = Bookmarks(get_current_user_object())
        bms.add_bookmark('Last edited',
                         item.title,
                         '/view/' + item.path,
                         move_to_top=True,
                         limit=app.config['LAST_EDITED_BOOKMARK_LIMIT']).save_bookmarks()
    copy_default_rights(item.id, item_type)
    return item


def get_templates_for_folder(folder: Folder) -> List[DocEntry]:
    current_path = folder.path
    timdb = get_timdb()
    templates = []
    while True:
        for t in get_documents(filter_ids=get_viewable_blocks_or_none_if_admin(),
                               filter_folder=current_path + '/Templates',
                               search_recursively=False):
            if t.short_name not in (DOC_DEFAULT_RIGHT_NAME, FOLDER_DEFAULT_RIGHT_NAME):
                templates.append(t)
        if current_path == '':
            break
        current_path, short_name = timdb.folders.split_location(current_path)

        # Templates should not be templates of templates themselves. We skip them.
        # TODO Think if this needs a while loop in case of path like Templates/Templates/Templates
        if short_name == 'Templates':
            current_path, short_name = timdb.folders.split_location(current_path)
    templates.sort(key=lambda d: d.short_name.lower())
    return templates


def do_create_document(item_path, item_type, item_title, copied_doc: Optional[DocInfo], template_name):
    item = create_item(item_path,
                       item_type,
                       item_title,
                       DocEntry.create if item_type == 'document' else Folder.create,
                       get_current_user_group())

    if copied_doc:
        item.document.update(copied_doc.document.export_markdown(), item.document.export_markdown())
        for tr in copied_doc.translations:  # type: Translation
            doc_id = item.id
            if not tr.is_original_translation:
                doc_entry = DocEntry.create(None, get_current_user_group(), None)
                doc_entry.document.update(tr.document.export_markdown(), doc_entry.document.export_markdown())
                settings = doc_entry.document.get_settings()
                settings.set_source_document(item.id)
                doc_entry.document.set_settings(settings.get_dict())
                doc_id = doc_entry.id
            if tr.lang_id or not tr.is_original_translation:
                new_tr = Translation(doc_id=doc_id, src_docid=item.id, lang_id=tr.lang_id)
                new_tr.title = tr.title
                db.session.add(new_tr)
            if not tr.is_original_translation:
                copy_default_rights(doc_id, blocktypes.DOCUMENT, commit=False)
        db.session.commit()
    else:
        templates = get_templates_for_folder(item.parent)
        matched_templates = None
        if template_name:
            matched_templates = list(filter(lambda t: t.short_name == template_name, templates))
        if not matched_templates:
            matched_templates = list(filter(lambda t: t.short_name == FORCED_TEMPLATE_NAME, templates))
        if matched_templates:
            template = matched_templates[0]
            item.document.update(template.document.export_markdown(), item.document.export_markdown())

    return json_response(item)
