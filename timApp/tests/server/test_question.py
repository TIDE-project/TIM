from lxml import html

from tests.server.timroutetest import TimRouteTest
from tests.timliveserver import TimLiveServer


class QuestionTest(TimLiveServer, TimRouteTest):
    def test_question_html(self):
        self.login_test1()
        d = self.create_doc(from_file='example_docs/questions.md')
        pars = d.document.get_paragraphs()
        data = self.get('/view/' + d.path, as_tree=True)
        first_id = pars[0].get_id()
        expected_html_template = """
<div class="par questionPar"
     id="{0}"
     t="{1}"
     attrs="{{&#34;plugin&#34;: &#34;qst&#34;, &#34;question&#34;: &#34;true&#34;, &#34;taskId&#34;: &#34;test1&#34;}}">
    <a href="#{2}" title="Permlink" class="headerlink">#</a>
    <div class="parContent" id="{2}">
        <a class="questionAddedNew"><span class="glyphicon glyphicon-question-sign" title="Today"></span></a>
        <p class="questionNumber">Today</p>
    </div>
    <div class="editline" title="Click to edit this paragraph"></div>
    <div class="readline"
         title="Click to mark this paragraph as read"></div>
</div>
        """
        expected_element = html.fromstring(
            expected_html_template.format(
                first_id,
                pars[0].get_hash(),
                'test1'))
        self.assert_elements_equal(expected_element, data.cssselect('#' + first_id)[0])

        second_id = pars[1].get_id()
        result = data.cssselect('#{} .parContent qst-runner'.format(second_id))
        self.assertEqual(1, len(result))

        expected_element = html.fromstring(
            """
            <div class="par questionPar"
                 id="{0}"
                 t="{1}"
                 attrs="{{&#34;question&#34;: &#34;true&#34;, &#34;taskId&#34;: &#34;test3&#34;}}" ng-non-bindable>
                <a href="#{2}" title="Permlink" class="headerlink">#</a>
                <div class="parContent" id="{2}">
                    <div class="error">This question is missing plugin="qst" attribute. Please add it.</div>
                </div>
                <div class="editline" title="Click to edit this paragraph"></div>
                <div class="readline"
                     title="Click to mark this paragraph as read"></div>
            </div>
                    """.format(
                pars[2].get_id(),
                pars[2].get_hash(),
                'test3'))
        self.assert_elements_equal(expected_element, data.cssselect('#' + pars[2].get_id())[0])

        self.get('/getQuestionByParId',
                 query_string={'doc_id': d.id, 'par_id': first_id},
                 expect_content={'markup': {'json': {'answerFieldType': 'radio',
                                                     'headers': [],
                                                     'matrixType': '',
                                                     'questionText': 'What day is it today?',
                                                     'questionTitle': 'Today',
                                                     'questionType': 'radio-vertical',
                                                     'rows': ['Monday', 'Wednesday', 'Friday'],
                                                     'timeLimit': 90},
                                            'points': '2:1',
                                            'qst': False,
                                            'taskId': 'test1'}})

        self.get('/getQuestionByParId',
                 query_string={'doc_id': d.id, 'par_id': second_id},
                 expect_content={'markup': {'json': {'answerFieldType': 'radio',
                                                     'headers': [],
                                                     'matrixType': '',
                                                     'questionText': 'What day is it today?',
                                                     'questionTitle': 'Today',
                                                     'questionType': 'radio-vertical',
                                                     'rows': ['Monday', 'Wednesday', 'Friday'],
                                                     'timeLimit': 90},
                                            'points': '2:1',
                                            'qst': True,
                                            'taskId': 'test2'}})

        self.get('/getQuestionByParId',
                 query_string={'doc_id': d.id, 'par_id': pars[2].get_id()},
                 expect_status=400,
                 expect_content={'error': 'Paragraph is not a plugin: {}'.format(pars[2].get_id())})

        normal_par_id = pars[3].get_id()
        self.get('/getQuestionByParId',
                 query_string={'doc_id': d.id, 'par_id': normal_par_id},
                 expect_status=400,
                 expect_content={'error': 'Paragraph is not a plugin: {}'.format(normal_par_id)})
