"""Routes for editing a document."""
from bs4 import UnicodeDammit
from flask import Blueprint

from .common import *
from documentmodel.docparagraph import DocParagraph
from documentmodel.documentparser import DocumentParser
from markdownconverter import md_to_html
import pluginControl
from timdb.docidentifier import DocIdentifier
from timdb.timdbbase import TimDbException

edit_page = Blueprint('edit_page',
                      __name__,
                      url_prefix='')  # TODO: Better URL prefix.


@edit_page.route('/update/<int:doc_id>/<version>', methods=['POST'])
def update_document(doc_id, version):
    """Route for updating a document as a whole.

    :param doc_id: The id of the document to be modified.
    :param version: The version string of the current document version.
    :return: A JSON object containing the versions of the document.
    """
    timdb = getTimDb()
    doc_identifier = DocIdentifier(doc_id, version)
    if not timdb.documents.exists(doc_id):
        abort(404)
    if not timdb.users.userHasEditAccess(getCurrentUserId(), doc_id):
        abort(403)
    # verify_document_version(doc_id, version)
    if 'file' in request.files:
        doc = request.files['file']
        raw = doc.read()

        # UnicodeDammit gives incorrect results if the encoding is UTF-8 without BOM,
        # so try the built-in function first.
        try:
            content = raw.decode('utf-8')
        except UnicodeDecodeError:
            content = UnicodeDammit(raw).unicode_markup
    else:
        request_json = request.get_json()
        if 'fulltext' not in request_json:
            return jsonResponse({'message': 'Malformed request - fulltext missing.'}, 400)
        content = request_json['fulltext']

    if content is None:
        return jsonResponse({'message': 'Failed to convert the file to UTF-8.'}, 400)
    doc = Document(doc_id, modifier_group_id=getCurrentUserGroup())
    try:
        d = timdb.documents.update_document(doc, content)
    except TimDbException as e:
        abort(400, str(e))
        return
    chg = d.get_changelog()
    for ver in chg:
        ver['group'] = timdb.users.get_user_group_name(ver.pop('group_id'))
    return jsonResponse({'versions': chg, 'fulltext': d.export_markdown()})


@edit_page.route("/postParagraph/", methods=['POST'])
def modify_paragraph():
    """
    Route for modifying a paragraph in a document.

    :return: A JSON object containing the paragraphs in HTML form along with JS, CSS and Angular module dependencies.
    """
    timdb = getTimDb()
    doc_id, md, par_id, par_next_id, attrs = verify_json_params('docId', 'text', 'par', 'par_next', 'attrs')
    verifyEditAccess(doc_id)

    current_app.logger.info("Editing file: {}, paragraph {}".format(doc_id, par_id))
    version = request.headers.get('Version', '')
    # verify_document_version(doc_id, version)
    doc = get_newest_document(doc_id)
    if not doc.has_paragraph(par_id):
        abort(400, 'Paragraph not found: ' + par_id)

    editor_pars = get_pars_from_editor_text(doc_id, md)
    original_par = DocParagraph(doc_id=doc_id, par_id=par_id)
    pars = []
    if editor_pars[0].is_different_from(original_par):
        [par], _ = timdb.documents.modify_paragraph(doc,
                                                    par_id,
                                                    editor_pars[0].get_markdown(),
                                                    editor_pars[0].get_attrs())
        pars.append(par)

    for p in editor_pars[1:]:
        [par], _ = timdb.documents.add_paragraph(doc, p.get_markdown(), par_next_id, attrs=p.get_attrs())
        pars.append(par)

    # Replace appropriate elements with plugin content, load plugin requirements to template
    pars, js_paths, css_paths, modules = pluginControl.pluginify(pars,
                                                                 getCurrentUserName(),
                                                                 timdb.answers,
                                                                 doc_id,
                                                                 getCurrentUserId())
    return jsonResponse({'texts': pars,
                         'js': js_paths,
                         'css': css_paths,
                         'angularModule': modules,
                         'version': doc.get_version()})


@edit_page.route("/preview/<int:doc_id>", methods=['POST'])
def preview(doc_id):
    """Route for previewing a paragraph.

    :param doc_id: The id of the document in which the preview will be renderer. Unused so far.
    :return: A JSON object containing the paragraphs in HTML form along with JS, CSS and Angular module dependencies.
    """
    timdb = getTimDb()
    text, = verify_json_params('text')
    blocks = get_pars_from_editor_text(doc_id, text)
    pars, js_paths, css_paths, modules = pluginControl.pluginify(blocks,
                                                                 getCurrentUserName(),
                                                                 timdb.answers,
                                                                 doc_id,
                                                                 getCurrentUserId())
    return jsonResponse({'texts': pars,
                         'js': js_paths,
                         'css': css_paths,
                         'angularModule': modules})


def get_pars_from_editor_text(doc_id, text):
    blocks = [DocParagraph(doc_id=doc_id, md=par['md'], attrs=par.get('attrs'))
              for par in DocumentParser(text).get_blocks(break_on_code_block=False,
                                                         break_on_header=False,
                                                         break_on_normal=False)]
    return blocks


@edit_page.route("/newParagraph/", methods=["POST"])
def add_paragraph():
    """Route for adding a new paragraph to a document.

    :return: A JSON object containing the paragraphs in HTML form along with JS, CSS and Angular module dependencies.
    """
    timdb = getTimDb()
    md, doc_id, par_next_id = verify_json_params('text', 'docId', 'par_next')
    verifyEditAccess(doc_id)
    version = request.headers.get('Version', '')
    editor_pars = get_pars_from_editor_text(doc_id, md)

    # verify_document_version(doc_id, version)
    doc = get_newest_document(doc_id)
    pars = []
    for p in editor_pars:
        [par], _ = timdb.documents.add_paragraph(doc, p.get_markdown(), par_next_id, attrs=p.get_attrs())
        pars.append(par)
    pars, js_paths, css_paths, modules = pluginControl.pluginify(pars,
                                                                 getCurrentUserName(),
                                                                 timdb.answers,
                                                                 doc_id,
                                                                 getCurrentUserId())
    return jsonResponse({'texts': pars,
                         'js': js_paths,
                         'css': css_paths,
                         'angularModule': modules,
                         'version': doc.get_version()})


@edit_page.route("/deleteParagraph/<int:doc_id>/<par_id>", methods=["POST"])
def delete_paragraph(doc_id, par_id):
    """Route for deleting a paragraph from a document.

    :param doc_id: The id of the document.
    :param par_id: The id of the paragraph.
    :return: A JSON object containing the version of the new document.
    """
    timdb = getTimDb()
    verifyEditAccess(doc_id)
    version = request.headers.get('Version', '')
    # verify_document_version(doc_id, version)
    new_doc = timdb.documents.delete_paragraph(get_newest_document(doc_id), par_id)
    return jsonResponse({'version': new_doc.get_version()})
