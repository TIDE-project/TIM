from unittest import TestCase
from timApp.answer.routes import widen_fields
from timApp.answer.routes import get_alias

class TestWiden_fields(TestCase):
    def test_comparesame(self):
        pass
        #  self.assertEqual(True, compare_same("cat", "cat", 0), "t0")

    def test_widen_fields(self):
        s1 = ["d1"]
        e1 = ["d1"]

        r1 = widen_fields(s1)
        self.assertEqual(e1, r1, "Not same in normal case")

    def test_widen_fields1(self):
        s1 = ["d(1,3)"]
        e1 = ["d1", "d2"]

        r1 = widen_fields(s1)
        self.assertEqual(e1, r1, "Not same range format")

    def test_widen_fields2(self):
        s1 = ["d(1,3).points"]
        e1 = ["d1.points", "d2.points"]

        r1 = widen_fields(s1)
        self.assertEqual(e1, r1, "Not same range format")

    def test_widen_fields3(self):
        s1 = ["543.d(1,3).points"]
        e1 = ["543.d1.points", "543.d2.points"]

        r1 = widen_fields(s1)
        self.assertEqual(e1, r1, "Not same range format with docid and points")

    def test_widen_fields4(self):
        s1 = ["189279.t(1,4).points[2018-04-06 15:66:94, 2019-06-05 12:12:12] = tp"]
        e1 = ["189279.t1.points[2018-04-06 15:66:94, 2019-06-05 12:12:12]=tp1",
              "189279.t2.points[2018-04-06 15:66:94, 2019-06-05 12:12:12]=tp2",
              "189279.t3.points[2018-04-06 15:66:94, 2019-06-05 12:12:12]=tp3"]

        r1 = widen_fields(s1)
        self.assertEqual(e1, r1, "Not same range format with docid, points and date")

    def test_widen_fields5(self):
        s1 = ["d(1,3) = d"]
        e1 = ["d1=d1", "d2=d2"]

        r1 = widen_fields(s1)
        self.assertEqual(e1, r1, "Not same range format and alias")

    def test_widen_fields6(self):
        r1 = widen_fields(["d1;d2;d(3,5)"])
        self.assertEqual(["d1", "d2", "d3", "d4"], r1, "Not same in semicolon line")

    def test_widen_fields7(self):
        r1 = widen_fields("d1;d2;d( 3, 5)")
        self.assertEqual(["d1", "d2", "d3", "d4"], r1, "Not same in semicolon line")

    ##############################################################
class Testget_alias(TestCase):

    def test_get_name1(self):
        self.assertEqual("d", get_alias("d"), "Not same in pure name")
        self.assertEqual("d3", get_alias("d3"), "Not same in pure name")

    def test_get_name2(self):
        self.assertEqual("d3", get_alias("543.d3.points"), "Not same with docid and points")

    def test_get_name3(self):
        self.assertEqual("t", get_alias("189279.t(1,4).points[2018-04-06 15:66:94, 2019-06-05 12:12:12]"), "Not same in copmplex version")

    def test_get_name4(self):
        self.assertEqual("t3", get_alias("189279.t3.points[2018-04-06 15:66:94, 2019-06-05 12:12:12]"), "Not same with points and date")

    def test_get_name5(self):
        self.assertEqual("t3", get_alias("189279.t3.[2018-04-06 15:66:94, 2019-06-05 12:12:12]"), "Not same with date")

    def test_get_name6(self):
        self.assertEqual("t3", get_alias("189279.t3.points"), "Not same with points")

    def test_get_name7(self):
        self.assertEqual("t4", get_alias("t4.points"), "Not same with just points")
