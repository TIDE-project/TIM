__author__ = 'localadmin'

from contracts import contract
from timdb.timdbbase import TimDbBase
import json


class Lectures(TimDbBase):
    @contract
    def create_lecture(self, doc_id: "int", lecturer: 'int', start_time: "string", end_time: "string",
                       lecture_code: "string", password: "string", options: "string", commit: "bool") -> "int":
        cursor = self.db.cursor()

        cursor.execute("""
                          INSERT INTO Lecture(lecture_code, doc_id,lecturer, start_time, end_time, password, options)
                          VALUES (?,?,?,?,?,?,?)
                          """, [lecture_code, doc_id, lecturer, start_time, end_time, password, options])

        if commit:
            self.db.commit()
        lecture_id = cursor.lastrowid

        return lecture_id


    @contract
    def update_lecture(self, lecture_id: "int", doc_id: "int", lecturer: 'int', start_time: "string", end_time: "string",
                       lecture_code: "string", password: "string", options: "string"):

        cursor = self.db.cursor()

        cursor.execute("""
                        UPDATE Lecture
                        SET lecture_code = ?, doc_id = ?, lecturer = ?, start_time = ?, end_time = ?, password = ?,
                            options = ?
                        WHERE lecture_id = ?
                        """, [lecture_code, doc_id, lecturer, start_time, end_time, password, options, lecture_id])

        self.db.commit()
        return lecture_id

    @contract
    def delete_lecture(self, lecture_id: 'int', commit: 'bool'):
        cursor = self.db.cursor()

        cursor.execute(
            """
            DELETE
            FROM Lecture
            WHERE lecture_id = ?
            """, [lecture_id])

        if commit:
            self.db.commit()

    @contract
    def delete_users_from_lecture(self, lecture_id: 'int', commit: 'bool'=True):
        cursor = self.db.cursor()

        cursor.execute(
            """
            DELETE FROM LectureUsers
            WHERE lecture_id = ?
            """, [lecture_id]
        )

        if commit:
            self.db.commit()

    @contract
    def get_lecture(self, lecture_id: "int") -> 'list(dict)':
        cursor = self.db.cursor()

        cursor.execute(
            """
            SELECT *
            FROM Lecture
            WHERE lecture_id = ?
            """, [lecture_id]
        )

        return self.resultAsDictionary(cursor)

    @contract
    def get_lecture_by_name(self, lecture_code: "string", doc_id: "int") -> 'list(dict)':
        cursor = self.db.cursor()

        cursor.execute(
            """
            SELECT *
            FROM Lecture
            WHERE lecture_code = ? AND doc_id = ?
            """, [lecture_code, doc_id]
        )

        return self.resultAsDictionary(cursor)

    @contract
    def get_all_lectures_from_document(self, document_id:"int") -> 'list(dict)':
        cursor = self.db.cursor()

        cursor.execute(
            """
            SELECT *
            FROM Lecture
            WHERE doc_id = ?
            """, [document_id]
        )

        return self.resultAsDictionary(cursor)

    @contract
    def join_lecture(self, lecture_id: "int", user_id: "int", commit: "bool"=True):
        cursor = self.db.cursor()

        cursor.execute("""
                       INSERT INTO LectureUsers(lecture_id, user_id)
                       VALUES (?,?)
                       """, [lecture_id, user_id])
        if commit:
            self.db.commit()

    @contract
    def leave_lecture(self, lecture_id: "int", user_id: "int", commit: "bool"=True):
        cursor = self.db.cursor()

        cursor.execute("""
                       DELETE
                       FROM LectureUsers
                       WHERE lecture_id = ? AND user_id = ?
                       """, [lecture_id, user_id])

        if commit:
            self.db.commit()

    @contract
    def get_document_lectures(self, doc_id: 'int', time: 'string'):
        cursor = self.db.cursor()

        cursor.execute("""
                        SELECT lecture_code, start_time,end_time, password
                        FROM Lecture
                        WHERE doc_id = ? AND end_time > ?
                        ORDER BY lecture_code
                        """, [doc_id, time])

        return self.resultAsDictionary(cursor)

    @contract
    def get_all_lectures(self, time: 'str'):
        cursor = self.db.cursor()

        cursor.execute("""
                        SELECT lecture_code, start_time,end_time, password, lecturer
                        FROM Lecture
                        WHERE end_time > ?
                        ORDER BY lecture_code
                        """, [time])

        return self.resultAsDictionary(cursor)

    @contract
    def get_lecture_by_code(self, lecture_code: 'string', doc_id: 'int') -> 'int':
        cursor = self.db.cursor()

        cursor.execute("""
                        SELECT lecture_id, password
                        FROM Lecture
                        WHERE lecture_code = ? AND doc_id = ?
                        """, [lecture_code, doc_id])

        return cursor.fetchone()[0]

    @contract
    def check_if_correct_name(self, doc_id: 'int', lecture_code: 'string', lecture_id : 'int') -> 'int':
        cursor = self.db.cursor()

        cursor.execute("""
                        SELECT lecture_id
                        FROM Lecture
                        WHERE lecture_code = ? AND doc_id = ? AND lecture_id != ?
                        """, [lecture_code, doc_id, lecture_id])

        answer = cursor.fetchall()

        if len(answer) >= 1:
            return False

        return True

    @contract
    def set_end_for_lecture(self, lecture_id: "int", end_time: "string"):
        cursor = self.db.cursor()

        cursor.execute(
            """
            UPDATE Lecture
            SET end_time = ?
            WHERE lecture_id = ?
            """, [end_time, lecture_id]
        )

        self.db.commit()

    @contract
    def check_if_lecture_is_running(self, lecture_id: "int", now="string") -> bool:
        cursor = self.db.cursor()

        cursor.execute(
            """
            SELECT lecture_id
            FROM Lecture
            WHERE lecture_id = ? AND end_time > ?
            """, [lecture_id, now]
        )

        lecture_id = cursor.fetchall()
        if len(lecture_id) <= 0:
            return False

        return True

    @contract
    def check_if_lecture_is_full(self, lecture_id: "int") -> bool:
        cursor = self.db.cursor()

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM LectureUsers
            WHERE lecture_id == ?;
            """, [lecture_id]
        )

        students = int(cursor.fetchone()[0])

        cursor.execute(
            """
            SELECT options
            FROM Lecture
            WHERE Lecture_id == ?
            """, [lecture_id]
        )

        options = cursor.fetchone()
        options = json.loads(options[0])

        max = None
        if 'max_students' in options:
            max = int(options['max_students'])

        if max is None:
            return False
        else:
            return max > students

    @contract
    def check_if_in_lecture(self, doc_id: "int", user_id: "int") -> "tuple":
        """
        Check if user is in lecture from specific document
        :param doc_id: document id
        :param user_id: user id
        :return:
        """

        cursor = self.db.cursor()

        cursor.execute("""
                           SELECT lecture_id
                           FROM Lecture
                           WHERE doc_id = ?
                           """, [doc_id])

        lecture_ids = cursor.fetchall()
        if len(lecture_ids) <= 0:
            return False, 0

        string_of_lectures = ""
        comma = ""
        for lecture in lecture_ids:
            string_of_lectures += comma + str(lecture[0])
            comma = ","

        if len(string_of_lectures) <= 0:
            return False, -1

        cursor.execute("""
                           SELECT lecture_id, user_id
                           FROM LectureUsers
                           WHERE lecture_id IN """ + "(" + string_of_lectures + ")" + """ AND user_id = ?
                            """, [user_id])

        result = cursor.fetchall()
        if len(result) > 0:
            return True, result[0][0]
        else:
            return False, -1

    @contract
    def check_if_in_any_lecture(self, user_id: "int") -> "tuple":
        """
        Check if user is in lecture from specific document
        :param doc_id: document id
        :param user_id: user id
        :return:
        """

        cursor = self.db.cursor()

        cursor.execute("""
                           SELECT lecture_id, user_id
                           FROM LectureUsers
                           WHERE user_id = ?
                            """, [user_id])

        result = cursor.fetchall()
        if len(result) > 0:
            return True, result[0][0]
        else:
            return False, -1

    @contract
    def get_users_from_leture(self, lecture_id: "int") -> "list(dict)":
        cursor = self.db.cursor()

        cursor.execute("""
                            SELECT user_id
                            FROM LectureUsers
                            WHERE lecture_id = ?
                      """, [lecture_id])

        return self.resultAsDictionary(cursor)

    @contract
    def update_lecture_starting_time(self, lecture_id: "int", start_time: "string", commit: "bool"=True) -> "dict":
        cursor = self.db.cursor()

        cursor.execute("""
                        UPDATE Lecture
                        SET start_time = ?
                        WHERE lecture_id = ?
        """, [start_time, lecture_id])

        if commit:
            self.db.commit()

        cursor.execute("""
                      SELECT *
                      FROM Lecture
                      WHERE lecture_id = ?
        """, [lecture_id])

        return self.resultAsDictionary(cursor)[0]

    @contract
    def extend_lecture(self, lecture_id: "int", new_end_time: "string", commit: "bool"=True):
        cursor = self.db.cursor()

        cursor.execute("""
                        UPDATE Lecture
                        SET end_time = ?
                        WHERE lecture_id = ?
        """,[new_end_time, lecture_id])

        if commit:
            self.db.commit()

