import json
import os
import shutil

from documentmodel.document import Document
from documentmodel.docparagraph import DocParagraph
from documentmodel.documentwriter import DocumentParser, DocumentWriter
from documentmodel.randutils import hashfunc
from typing import Dict, Generic, List, Optional


class Clipboard:
    def __init__(self, files_root: str):
        self.files_root = files_root

    def get_path(self):
        return os.path.join(self.files_root, 'clipboard')

    def get(self, user_id: int):
        return Clipboard.UserClipboard(self, user_id)

    def clear_all(self):
        path = self.get_path()
        if os.path.exists(path):
            shutil.rmtree(path)

    class UserClipboard:
        def __init__(self, parent: 'Clipboard', user_id: int):
            self.user_id = user_id
            self.path = os.path.join(parent.get_path(), str(self.user_id))

        def get_clipfilename(self) -> str:
            return os.path.join(self.path, 'content')

        def get_reffilename(self) -> str:
            return os.path.join(self.path, 'ref-content')

        def clear(self):
            for name in (self.get_clipfilename(), self.get_reffilename()):
                if os.path.isfile(name):
                    os.remove(name)

        def read(self, as_ref: Optional[bool] = False) -> Optional[List[Dict[str, str]]]:
            clipfilename = self.get_reffilename() if as_ref else self.get_clipfilename()
            if not os.path.isfile(clipfilename):
                return None
            with open(clipfilename, 'rt', encoding='utf-8') as clipfile:
                content = clipfile.read()
            return DocumentParser(content).validate_structure(is_whole_document=False).get_blocks()

        def write(self, pars: List[Dict[str, Generic]]):
            os.makedirs(self.path, exist_ok=True)
            text = DocumentWriter(pars).get_text()
            with open(self.get_clipfilename(), 'wt', encoding='utf-8') as clipfile:
                clipfile.write(text)

        def write_refs(self, pars: List[DocParagraph]):
            os.makedirs(self.path, exist_ok=True)
            ref_pars = [p.create_reference(p.doc).dict() for p in pars]
            reftext = DocumentWriter(ref_pars).get_text()
            with open(self.get_reffilename(), 'wt', encoding='utf-8') as reffile:
                reffile.write(reftext)

        def write_arearef(self, doc: Document, area_name: str):
            os.makedirs(self.path, exist_ok=True)
            ref_pars = [DocParagraph.create_area_reference(doc, area_name).dict()]
            reftext = DocumentWriter(ref_pars).get_text()
            with open(self.get_reffilename(), 'wt', encoding='utf-8') as reffile:
                reffile.write(reftext)

        def copy_pars(self, doc: Document, par_start: str, par_end: str, area_name: Optional[str] = None):
            copying = False
            par_objs = []
            pars = []

            # todo: make the iterator accept ranges
            i = doc.__iter__()
            try:
                while True:
                    par = next(i)
                    if not copying and par.get_id() == par_start:
                        copying = True
                    if copying:
                        par_objs.append(par)
                        pars.append(par.dict())
                        if par.get_id() == par_end:
                            raise StopIteration
            except StopIteration:
                pass
            finally:
                i.close()

            self.write(pars)

            if area_name is None:
                self.write_refs(par_objs)
            else:
                self.write_arearef(par_objs[0].doc, area_name)

        def paste_before(self, doc: Document, par_id: Optional[str], as_ref: Optional[bool] = False) -> List[DocParagraph]:
            pars = self.read(as_ref)
            if pars is None:
                return
            doc_pars = []
            par_before = par_id
            for par in reversed(pars):
                # We need to reverse the sequence because we're inserting before, not after
                new_par = doc.insert_paragraph(par['md'], par_before, attrs=par.get('attrs'), properties=par.get('properties'))
                doc_pars = [new_par] + doc_pars
                par_before = new_par.get_id()

            return doc_pars

