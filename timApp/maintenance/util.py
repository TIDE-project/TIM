import sys
from argparse import ArgumentParser
from typing import Generator, Tuple, Optional, Callable, Union

from timApp.documentmodel.docparagraph import DocParagraph
from timApp.tim_app import app
from timApp.timdb.docinfo import DocInfo
from timApp.timdb.models.docentry import DocEntry
from timApp.timdb.models.folder import Folder
from timApp.timdb.timdbexception import TimDbException


class BasicArguments:
    def __init__(self):
        self.dryrun = False
        self.progress = False
        self.doc = ''
        self.folder = ''


def enum_docs(folder: Optional[Folder] = None) -> Generator[DocInfo, None, None]:
    visited_docs = set()
    if not folder:
        folder = Folder.get_root()
    for d in folder.get_all_documents(include_subdirs=True):
        for t in d.translations:
            if t.id in visited_docs:
                continue
            visited_docs.add(t.id)
            yield t


def iterate_pars_skip_exceptions(d: DocInfo):
    i = d.document.__iter__()
    while True:
        try:
            yield next(i)
        except StopIteration:
            raise
        except TimDbException as e:
            print(e)


def enum_pars(item: Union[Folder, DocInfo, None] = None) -> Generator[Tuple[DocInfo, DocParagraph], None, None]:
    if isinstance(item, Folder) or item is None:
        collection = enum_docs(item)
    else:
        collection = [item]
    for d in collection:
        for p in iterate_pars_skip_exceptions(d):
            yield d, p


def process_items(func: Callable[[DocInfo, BasicArguments], int], parser: ArgumentParser):
    opts: BasicArguments = parser.parse_args()
    with app.app_context():
        doc_to_fix = DocEntry.find_by_path(opts.doc, fallback_to_id=True,
                                           try_translation=True) if opts.doc is not None else None
        folder_to_fix = Folder.find_by_path(opts.folder, fallback_to_id=True) if opts.folder is not None else None
        if opts.doc is not None and not doc_to_fix:
            print('Document not found.')
            sys.exit(1)
        if opts.folder is not None and not folder_to_fix:
            print('Folder not found.')
            sys.exit(1)
        total_pars = 0
        if doc_to_fix:
            docs = [doc_to_fix]
        elif folder_to_fix:
            if opts.progress:
                print(f'Processing paragraphs in folder {folder_to_fix.path}')
            docs = enum_docs(folder=folder_to_fix)
        else:
            assert False
        for d in docs:
            if opts.progress:
                print(f'Processing document {d.path}')
            total_pars += func(d, opts)
        if hasattr(opts, 'dryrun'):
            print(f'Total paragraphs that {"would be" if opts.dryrun else "were"} affected: {total_pars}')
        else:
            print(f'Total paragraphs found: {total_pars}')


def create_argparser(description: str, readonly=False):
    parser = ArgumentParser(description=description)
    group_item = parser.add_mutually_exclusive_group(required=True)
    group_item.add_argument('--doc', help='doc id or path to process')
    group_item.add_argument('--folder', help='folder path or id to process')
    group_dryrun = parser.add_mutually_exclusive_group()
    if not readonly:
        group_dryrun.add_argument('--dry-run', dest='dryrun', action='store_true',
                                  help='show what would be fixed')
        group_dryrun.add_argument('--no-dry-run', dest='dryrun', action='store_false', help='do the fixes')
        group_dryrun.set_defaults(dryrun=True)
    parser.add_argument('--progress', dest='progress', action='store_true',
                        help='show progress')
    parser.set_defaults(progress=False)
    return parser
