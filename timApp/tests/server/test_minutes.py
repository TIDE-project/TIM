from timApp.admin.replace_in_documents import perform_replace, ReplaceArguments
from timApp.document.docentry import DocEntry
from timApp.document.specialnames import TEMPLATE_FOLDER_NAME, PRINT_FOLDER_NAME, PREAMBLE_FOLDER_NAME
from timApp.tests.server.timroutetest import TimRouteTest
from timApp.timdb.sqa import db
from timApp.user.usergroup import UserGroup
from timApp.util.utils import EXAMPLE_DOCS_PATH


class MinutesHandlingTest(TimRouteTest):

    def test_minutes_creation(self):
        # Tests creation of minutes based on a meeting invitation document
        self.login_test1()
        knro = 3
        d = self.create_doc(settings={"macros": {"knro": knro}})
        minutes_document_path = f"{d.location}/pk/pk{knro}"
        self.json_post("/minutes/createMinutes",
                       json_data={"item_path": minutes_document_path,
                                  "item_title": f"pk{knro}",
                                  "copy": d.id})
        d2 = DocEntry.find_by_path(minutes_document_path)
        chg = d2.document.get_changelog()
        self.assertEqual(self.get_test_user_1_group_id(), chg.entries[0].group_id)
        self.assertTrue(d2.document.get_settings().memo_minutes() == "minutes")

    def test_minute_extracts(self):
        # Tests creation of extracts from a full minutes document
        self.login_test1()
        ug1 = UserGroup.create('ittdk18', commit=False)
        ug2 = UserGroup.create('ittdk1', commit=False)
        u = self.current_user
        u.groups.append(ug1)
        u.groups.append(ug2)
        db.session.commit()
        knro = 9
        d_kokous = self.create_doc(path=self.get_personal_item_path('tdk/2018/kokous9'),
                                   from_file=f'{EXAMPLE_DOCS_PATH}/tdk/memo.md')
        d_lait = self.create_doc(path=self.get_personal_item_path('tdk/lait/lait'),
                                 from_file=f'{EXAMPLE_DOCS_PATH}/tdk/lait.md')
        d_preamble = self.create_doc(
            path=self.get_personal_item_path(f'tdk/{TEMPLATE_FOLDER_NAME}/{PREAMBLE_FOLDER_NAME}/preamble'),
            from_file=f'{EXAMPLE_DOCS_PATH}/tdk/preamble.md')
        d_preamble_year = self.create_doc(
            path=self.get_personal_item_path(f'tdk/2018/{TEMPLATE_FOLDER_NAME}/{PREAMBLE_FOLDER_NAME}/preamble'),
            from_file=f'{EXAMPLE_DOCS_PATH}/tdk/preamble_year.md')
        for d in (d_preamble, d_preamble_year):
            perform_replace(d, ReplaceArguments(term='LAIT_ID_HERE',
                                                to=f'{d_lait.id}'))
        for p in d_kokous.document.get_paragraphs():
            if p.get_attr('rd') == 'LAIT_ID_HERE':
                p.set_attr('rd', d_lait.id)
                p.save()

        self.get(f"/minutes/createMinuteExtracts/{d_kokous.path_without_lang}", expect_status=302,
                 expect_content=f'view/{d_kokous.location}/otteet/kokous{knro}/kokous{knro}')
        ote_index = DocEntry.find_by_path(f"{d_kokous.location}/otteet/kokous{knro}/kokous{knro}")
        t = self.get(ote_index.url, as_tree=True)
        self.assert_content(
            t,
            ['Kokoukset | Seuraava esityslista | pdf | Ohjeet | Keskustelu | Ylläpito',
             'Pöytäkirjan asiakohtien otteet',
             'Lista 1, (PDF) - Ilmoitusasiat\n'
             'Lista 2, (PDF) - Jaska Jokusen väitöskirjan arvostelu',
             '{"area_end": "kokous9"}'])
        self.assertEqual("""## Pöytäkirjan asiakohtien otteet {area="kokous9"}


- [Lista 1](lista1), ([PDF](/print/users/test-user-1/tdk/2018/otteet/kokous9/lista1)) - Ilmoitusasiat
- [Lista 2](lista2), ([PDF](/print/users/test-user-1/tdk/2018/otteet/kokous9/lista2)) - Jaska Jokusen väitöskirjan arvostelu

#- {area_end="kokous9"}
""", ote_index.document.export_markdown(export_ids=False))
        ote1 = DocEntry.find_by_path(f"{d_kokous.location}/otteet/kokous{knro}/lista1")
        self.assertEqual("""#- {rd="5" rp="dsENZazDtd1Z"}

#- {rd="5" rp="sEj1vkUWmFmG"}

#- {rd="5" rp="ePZZ1MvVVb5S"}

#- {rd="5" rp="RIam8d8VXbQv"}

#- {rd="5" rp="yN0j9XeEOdZG"}

#- {rd="5" rp="PJxELAyKhZuu"}

%%ALLEKIRJOITUKSET%%
""", ote1.document.export_markdown(export_ids=False))
        ote_html = self.get(ote1.url, as_tree=True)
        self.assert_content(
            ote_html,
            ['Kokoukset | Seuraava esityslista | pdf | Ohjeet | Keskustelu | Ylläpito',
             '!================!Page Break!================!\n'
             '\n'
             '\n'
             '\n'
             '\n'
             '\n'
             '\n'
             '\n'
             'JYVÄSKYLÄN YLIOPISTO\n'
             '9/2018\n'
             '\n'
             '\n'
             '\n'
             '\n'
             'Informaatioteknologian tiedekunta\n'
             '11.9.2018\n'
             '\n'
             '\n'
             'Tiedekuntaneuvosto\n'
             'Lista 1\n'
             '\n'
             '\n'
             '\n'
             '\n'
             'Asian valmistelija: Yliopistonopettaja Olli Ollinen, puh. 0400123456, '
             'olli.ollinen@example.com',
             '1. Ilmoitusasiat\n'
             '1.1 Dekaanin ja varadekaanin päätökset\n'
             '1.1.1 Tutkinnot vuonna 2018 (liite A/ lista 1)',
             'xxxHEXJSONxxx7b22686569676874223a2022363030222c2022766964656f69636f6e223a202246616c7365222c2022646f6374657874223a202229222c20226869646574657874223a20225069696c6f7461206c69697465222c202274657874223a20224b6f6b6f75732031312e392e32303138205c5c6e65776c696e65204c494954452041202f206c697374612031222c2022646f636c696e6b223a202268747470733a2f2f74696d2e6a79752e66692f66696c65732f7878782f7475746b696e6e6f742e706466222c20227769647468223a2022383030222c2022766964656f6e616d65223a2022284c494954452041202f206c6973746120312c222c20227374616d7065642d66696c65223a20224e6f6e65222c20226f70656e223a202246616c7365222c2022696672616d65223a202254727565222c20227374656d223a20225475746b696e6e6f742076756f6e6e612032303138222c202274797065223a20226c697374222c20227465787072696e74223a20222d205475746b696e6e6f742076756f6e6e61203230313820285b4c494954452041202f206c6973746120315d2868747470733a2f2f74696d2e6a79752e66692f66696c65732f7878782f7475746b696e6e6f742e7064662929222c202278646f6369636f6e223a202246616c7365222c202266696c65223a202268747470733a2f2f74696d2e6a79752e66692f66696c65732f7878782f7475746b696e6e6f742e706466222c20227461736b4944223a2022352e222c20227461736b4944457874223a2022352e2e65505a5a314d765656623553222c2022646f4c617a79223a202246616c7365222c2022757365725072696e74223a202246616c7365222c202270726576696577223a202246616c7365222c2022616e6f6e796d6f7573223a202254727565222c2022696e666f223a20224e6f6e65222c2022757365725f6964223a2022746573747573657231222c2022746172676574466f726d6174223a20226c61746578222c2022726576696577223a202246616c7365227d',
             'Kandidaatin tutkinnot: Toteutunut yhteensä xxx (tavoite 2018: yyy)\n'
             'Kauppatieteiden kandidaatin tutkinto: Toteutunut xx\n'
             '1.1.2 Arvostellut pro gradu –tutkielmat (liite B/ lista 1)',
             'xxxHEXJSONxxx7b22686569676874223a2022363030222c2022766964656f69636f6e223a202246616c7365222c2022646f6374657874223a202229222c20226869646574657874223a20225069696c6f7461206c69697465222c202274657874223a20224b6f6b6f75732031312e392e32303138205c5c6e65776c696e65204c494954452042202f206c697374612031222c2022646f636c696e6b223a202268747470733a2f2f74696d2e6a79752e66692f66696c65732f7979792f6772616475742e706466222c20227769647468223a2022383030222c2022766964656f6e616d65223a2022284c494954452042202f206c6973746120312c222c20227374616d7065642d66696c65223a20224e6f6e65222c20226f70656e223a202246616c7365222c2022696672616d65223a202254727565222c20227374656d223a20224172766f7374656c6c75742070726f206772616475205c75323031337475746b69656c6d6174222c202274797065223a20226c697374222c20227465787072696e74223a20222d204172766f7374656c6c75742070726f206772616475205c75323031337475746b69656c6d617420285b4c494954452042202f206c6973746120315d2868747470733a2f2f74696d2e6a79752e66692f66696c65732f7979792f6772616475742e7064662929222c202278646f6369636f6e223a202246616c7365222c202266696c65223a202268747470733a2f2f74696d2e6a79752e66692f66696c65732f7979792f6772616475742e706466222c20227461736b4944223a2022352e222c20227461736b4944457874223a2022352e2e794e306a395865454f645a47222c2022646f4c617a79223a202246616c7365222c2022757365725072696e74223a202246616c7365222c202270726576696577223a202246616c7365222c2022616e6f6e796d6f7573223a202254727565222c2022696e666f223a20224e6f6e65222c2022757365725f6964223a2022746573747573657231222c2022746172676574466f726d6174223a20226c61746578222c2022726576696577223a202246616c7365227d',
             'Esitys\nTodetaan ilmoitusasiat.',
             '%%ALLEKIRJOITUKSET%%'])

        DocEntry.create(f'{TEMPLATE_FOLDER_NAME}/{PRINT_FOLDER_NAME}/runko', initial_par="""
``` {.latex printing_template=""}
$body$
```""")
        db.session.commit()
        ote1_tex = self.get_no_warn(f'/print/{ote1.path}',
                                    query_string={'file_type': 'latex'})
        self.assertEqual(r"""
\pagebreak
\begin{tabular}{p{10cm} l}
JYVÄSKYLÄN YLIOPISTO              & Asialista 9/2018 \\
Informaatioteknologian tiedekunta & 11.9.2018         \\
Tiedekuntaneuvosto                & Lista 1\end{tabular}

{\valmistelija{Asian valmistelija: Yliopistonopettaja Olli Ollinen, puh.
0400123456,
\href{mailto:olli.ollinen@example.com}{\nolinkurl{olli.ollinen@example.com}}}}

\hypertarget{ilmoitusasiat}{%
\section{Ilmoitusasiat}\label{ilmoitusasiat}}

\hypertarget{dekaanin-ja-varadekaanin-puxe4uxe4tuxf6kset}{%
\subsection{Dekaanin ja varadekaanin
päätökset}\label{dekaanin-ja-varadekaanin-puxe4uxe4tuxf6kset}}

\hypertarget{tutkinnot-vuonna-2018-liite-a-lista-1}{%
\subsubsection{Tutkinnot vuonna 2018 (liite A/ lista
1)}\label{tutkinnot-vuonna-2018-liite-a-lista-1}}

\begin{itemize}
\tightlist
\item
  Tutkinnot vuonna 2018
  (\href{https://tim.jyu.fi/files/xxx/tutkinnot.pdf}{LIITE A / lista 1})
\end{itemize}

Kandidaatin tutkinnot: Toteutunut yhteensä xxx (tavoite 2018: yyy)

Kauppatieteiden kandidaatin tutkinto: Toteutunut xx

\hypertarget{arvostellut-pro-gradu-tutkielmat-liite-b-lista-1}{%
\subsubsection{Arvostellut pro gradu --tutkielmat (liite B/ lista
1)}\label{arvostellut-pro-gradu-tutkielmat-liite-b-lista-1}}

\begin{itemize}
\tightlist
\item
  Arvostellut pro gradu --tutkielmat
  (\href{https://tim.jyu.fi/files/yyy/gradut.pdf}{LIITE B / lista 1})
\end{itemize}

\textbf{Esitys}

Todetaan ilmoitusasiat.

        """.strip(), ote1_tex)
        ote2 = DocEntry.find_by_path(f"{d_kokous.location}/otteet/kokous{knro}/lista2")
        ote2_tex = self.get_no_warn(f'/print/{ote2.path}',
                                    query_string={'file_type': 'latex'})
        self.assertEqual(r"""
\pagebreak
\begin{tabular}{p{10cm} l}
JYVÄSKYLÄN YLIOPISTO              & Asialista 9/2018 \\
Informaatioteknologian tiedekunta & 11.9.2018         \\
Tiedekuntaneuvosto                & Lista 2\end{tabular}

{\valmistelija{Asian valmistelijat: Opintopäällikkö Seppo Sepponen puh.
0500123456,
\href{mailto:seponasiat@example.com}{\nolinkurl{seponasiat@example.com}},
Yliopistonopettaja Olli Ollinen, puh. 0400123456,
\href{mailto:olli.ollinen@example.com}{\nolinkurl{olli.ollinen@example.com}}}}

\hypertarget{jaska-jokusen-vuxe4ituxf6skirjan-arvostelu}{%
\section{Jaska Jokusen väitöskirjan
arvostelu}\label{jaska-jokusen-vuxe4ituxf6skirjan-arvostelu}}

Jaska Jokunen puolustaa 1.1.2018 julkisessa väitöstilaisuudessa
tietojärjestelmätieteen väitöskirjaansa.

\laki{

}

\laki{

\laki{

Arvostelu, tekstikappale 1.

Arvostelu, tekstikappale 2.

Arvostelu, tekstikappale 3.

}

}

\laki{

}

\begin{itemize}
\tightlist
\item
  Vastaväittäjän lausunto
  (\href{https://tim.jyu.fi/files/zzz/opponentti.pdf}{LIITE A / lista
  2})
\end{itemize}

\textbf{Esitys}

Tiedekuntaneuvosto arvostelee Jaska Jokusen väitöskirjan.

        """.strip(), ote2_tex)
        self.assertIsNone(DocEntry.find_by_path(f"{d_kokous.location}/otteet/kokous{knro}/lista3"))
