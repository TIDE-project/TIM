from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any, Union

from flask import Response
from sqlalchemy import true
from sqlalchemy.orm import joinedload

from timApp.auth.accesshelper import verify_comment_right, verify_logged_in, get_doc_or_abort, \
    AccessDenied, verify_teacher_access, has_manage_access
from timApp.auth.accesshelper import verify_view_access
from timApp.auth.sessioninfo import get_current_user_object
from timApp.document.caching import clear_doc_cache
from timApp.document.docentry import DocEntry
from timApp.document.docinfo import DocInfo
from timApp.document.document import Document
from timApp.document.editing.routes import par_response
from timApp.folder.folder import Folder
from timApp.item.block import Block
from timApp.markdown.markdownconverter import md_to_html
from timApp.note.notes import tagstostr
from timApp.note.usernote import get_comment_by_id, UserNote
from timApp.notification.notification import NotificationType
from timApp.notification.notify import notify_doc_watchers
from timApp.notification.pending_notification import PendingNotification
from timApp.timdb.exceptions import TimDbException
from timApp.timdb.sqa import db
from timApp.user.user import User
from timApp.util.flask.requesthelper import get_referenced_pars_from_req, RouteException, NotExist
from timApp.util.flask.responsehelper import json_response
from timApp.util.flask.typedblueprint import TypedBlueprint
from timApp.util.utils import get_current_time

notes = TypedBlueprint(
    'notes',
    __name__,
    url_prefix='',
)

KNOWN_TAGS = ['difficult', 'unclear']


def has_note_edit_access(n: UserNote) -> bool:
    d = get_doc_or_abort(n.doc_id)
    g = get_current_user_object().get_personal_group()
    return n.usergroup == g or has_manage_access(d)


def get_comment_and_check_exists(note_id: int) -> UserNote:
    note = get_comment_by_id(note_id)
    if not note:
        raise NotExist('Comment not found. It may have been deleted.')
    return note


@notes.route("/note/<int:note_id>")
def get_note(note_id: int) -> Response:
    note = get_comment_and_check_exists(note_id)
    if not has_note_edit_access(note):
        raise AccessDenied()
    return json_response({'text': note.content, 'extraData': note}, date_conversion=True)


@dataclass
class DeletedNote:
    notification: PendingNotification

    @property
    def access(self) -> str:
        return 'everyone'

    def to_json(self) -> Dict[str, Any]:
        d = self.notification.block.docentries[0]
        return {
            'id': None,
            'doc_id': self.notification.doc_id,
            'doc_title': d.title,
            'par_id': self.notification.par_id,
            'par_hash': None,
            'content': self.notification.text,
            'created': None,
            'modified': None,
            'deleted_on': self.notification.created,
            'access': 'everyone',
            'usergroup': None,
            'user_who_deleted': self.notification.user,
            'url': d.url + '#' + self.notification.par_id,
        }


@notes.route("/notes/<path:item_path>")
def get_notes(
        item_path: str,
        private: bool = False,
        deleted: bool = False,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
) -> Response:
    """Gets all notes in a document or folder.

    :param item_path: Path of the item.
    :param private: Whether private comments should be included; only usable for admins
    :param deleted: Whether deleted public comments should be included
    :param start: Start timestamp of notes.
    :param end: End timestamp of notes.
    """
    i: Optional[Union[Folder, DocInfo]] = Folder.find_by_path(item_path)
    if not i:
        i = DocEntry.find_by_path(item_path)
    if not i:
        raise RouteException('Item not found.')
    u = get_current_user_object()
    if isinstance(i, Folder):
        all_docs = i.get_all_documents(
            include_subdirs=True,
        )
        if not all(u.has_teacher_access(d) for d in all_docs):
            raise AccessDenied('You do not have teacher access to all documents in this folder.')
        docs = all_docs
    else:
        verify_teacher_access(i)
        docs = [i]
    access_restriction = UserNote.access == 'everyone'
    if private:
        access_restriction = true()
    time_restriction = true()
    if start:
        time_restriction = time_restriction & (UserNote.created >= start)
    if end:
        time_restriction = time_restriction & (UserNote.created < end)
    d_ids = [d.id for d in docs]
    ns = (UserNote.query
          .filter(UserNote.doc_id.in_(d_ids) & access_restriction & time_restriction)
          .options(joinedload(UserNote.usergroup))
          .options(joinedload(UserNote.block).joinedload(Block.docentries))
          .all())
    all_count = len(ns)
    if not u.is_admin:
        ns = [n for n in ns if n.access == 'everyone']
    if deleted:
        deleted_notes = list(map(DeletedNote, PendingNotification.query.filter(PendingNotification.doc_id.in_(d_ids) & (
                    PendingNotification.kind == NotificationType.CommentDeleted)).options(
            joinedload(PendingNotification.block).joinedload(Block.docentries)).all()))
        ns += deleted_notes
        all_count += len(deleted_notes)
    public_count = 0
    deleted_count = 0
    for n in ns:
        if isinstance(n, DeletedNote):
            deleted_count += 1
        if n.access == 'everyone':
            public_count += 1
    extra = {}
    if deleted:
        extra['deleted_everyone'] = deleted_count
        extra['not_deleted_everyone'] = public_count - deleted_count
    if private:
        extra['justme'] = all_count - public_count
    return json_response({
        'counts': {
            **extra,
            'everyone': public_count,
            'all': all_count,
        },
        'notes': ns,
    })


def check_note_access_ok(is_public: bool, doc: Document) -> None:
    if is_public and doc.get_settings().comments() == 'private':
        raise AccessDenied('Only private comments can be posted on this document.')


def clear_doc_cache_after_comment(docinfo: DocInfo, user: User, is_public: bool) -> None:
    if is_public:
        clear_doc_cache(docinfo, user=None)
    else:
        clear_doc_cache(docinfo, user)


@notes.route("/postNote", methods=['POST'])
def post_note(
        text: str,
        access: str,
        docId: int,
        par: str,
        tags: Optional[Dict[str, bool]] = None,
) -> Response:
    is_public = access == "everyone"
    got_tags = []
    for tag in KNOWN_TAGS:
        if tags and tags.get(tag):
            got_tags.append(tag)
    doc_id = docId
    docinfo = get_doc_or_abort(doc_id)
    verify_comment_right(docinfo)
    doc = docinfo.document
    check_note_access_ok(is_public, doc)
    try:
        p = doc.get_paragraph(par)
    except TimDbException as e:
        raise NotExist(str(e))

    p = get_referenced_pars_from_req(p)[0]
    curr_user = get_current_user_object()
    n = UserNote(usergroup=curr_user.get_personal_group(),
                 doc_id=p.get_doc_id(),
                 par_id=p.get_id(),
                 par_hash=p.get_hash(),
                 content=text,
                 access=access,
                 html=md_to_html(text),
                 tags=tagstostr(got_tags))
    db.session.add(n)

    if is_public:
        notify_doc_watchers(docinfo, text, NotificationType.CommentAdded, p)
    clear_doc_cache_after_comment(docinfo, curr_user, is_public)
    return par_response([doc.get_paragraph(par)],
                        docinfo)


@notes.route("/editNote", methods=['POST'])
def edit_note(
        id: int,
        text: str,
        access: str,
        tags: Optional[Dict[str, bool]] = None,
) -> Response:
    verify_logged_in()
    note_id = id
    n = get_comment_and_check_exists(note_id)
    d = get_doc_or_abort(n.doc_id)
    verify_view_access(d)
    par_id = n.par_id
    is_public = access == "everyone"
    check_note_access_ok(is_public, d.document)
    try:
        par = d.document.get_paragraph(par_id)
    except TimDbException as e:
        raise RouteException(str(e))

    got_tags = []
    for tag in KNOWN_TAGS:
        if tags and tags.get(tag):
            got_tags.append(tag)
    if not has_note_edit_access(n):
        raise AccessDenied("Sorry, you don't have permission to edit this note.")
    n.content = text
    n.html = md_to_html(text)
    was_public = n.is_public
    n.access = access
    n.tags = tagstostr(got_tags)
    n.modified = get_current_time()

    if n.is_public:
        notify_doc_watchers(d, text, NotificationType.CommentModified, par)
    clear_doc_cache_after_comment(d, get_current_user_object(), is_public or was_public)
    doc = d.document
    return par_response([doc.get_paragraph(par_id)],
                        d)


@notes.route("/deleteNote", methods=['POST'])
def delete_note(
        docId: int,
        id: int,
        par: str,
) -> Response:
    doc_id, note_id, paragraph_id = docId, id, par
    note = get_comment_and_check_exists(note_id)
    d = get_doc_or_abort(doc_id)
    if not has_note_edit_access(note):
        raise AccessDenied("Sorry, you don't have permission to remove this note.")
    par_id = note.par_id
    try:
        p = d.document.get_paragraph(par_id)
    except TimDbException:
        raise RouteException('Cannot delete the note because the paragraph has been deleted.')
    db.session.delete(note)
    is_public = note.is_public
    if is_public:
        notify_doc_watchers(d, note.content, NotificationType.CommentDeleted, p)
    clear_doc_cache_after_comment(d, get_current_user_object(), is_public)
    doc = d.document
    return par_response([doc.get_paragraph(paragraph_id)],
                        d)
