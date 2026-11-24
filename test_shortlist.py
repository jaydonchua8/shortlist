import datetime as dt
import unittest
from shortlist import Index, Opportunity, Student, check, tokens
from gen import catalog, students

T = dt.date(2026, 11, 1)


def opp(i, title, text="", **kw):
    return Opportunity(i, title, text, **kw)


class Rules(unittest.TestCase):
    def setUp(self):
        self.s = Student(grade=10, state="IL", interests="robotics", citizen=False, budget=100)

    def test_eligible(self):
        self.assertEqual(check(opp(0, "x", deadline="2026-12-01"), self.s, T), [])

    def test_deadline_is_inclusive(self):
        self.assertEqual(check(opp(0, "x", deadline="2026-11-01"), self.s, T), [])
        self.assertEqual(check(opp(0, "x", deadline="2026-10-31"), self.s, T), ["deadline passed"])

    def test_each_rule(self):
        self.assertEqual(check(opp(0, "x", grades=(11, 12)), self.s, T), ["grade"])
        self.assertEqual(check(opp(0, "x", states=("CA", "NY")), self.s, T), ["state"])
        self.assertEqual(check(opp(0, "x", states=("CA", "IL")), self.s, T), [])
        self.assertEqual(check(opp(0, "x", citizens_only=True), self.s, T), ["citizenship"])
        self.assertEqual(check(opp(0, "x", cost=101), self.s, T), ["cost"])
        self.assertEqual(check(opp(0, "x", cost=100), self.s, T), [])

    def test_all_reasons_reported(self):
        o = opp(0, "x", grades=(12,), states=("CA",), citizens_only=True, cost=500, deadline="2026-01-01")
        self.assertEqual(check(o, self.s, T), ["deadline passed", "grade", "state", "citizenship", "cost"])


class Search(unittest.TestCase):
    def setUp(self):
        self.opps = [
            opp(0, "Robotics Summer Program", "build an autonomous robot with a team"),
            opp(1, "Poetry Fellowship", "write poetry and fiction with an editor"),
            opp(2, "Robotics Competition", "robot robot robot", grades=(12,)),
            opp(3, "Drone Internship", "autonomous drone sensor work", deadline="2026-10-01"),
            opp(4, "General Scholarship", "open to all students"),
        ]
        self.idx = Index(self.opps)
        self.s = Student(grade=10, state="IL", interests="I like robots and autonomous drones")

    def test_tokens(self):
        self.assertEqual(tokens("I like Robots and autonomous drones!"), ["robot", "autonomous", "drone"])

    def test_pre_filter_only_returns_eligible(self):
        ids = [r.opp.id for r in self.idx.search(self.s, T)]
        self.assertEqual(ids, [0])

    def test_no_filter_returns_ineligible_too(self):
        ids = {r.opp.id for r in self.idx.search(self.s, T, filter="none")}
        self.assertEqual(ids, {0, 2, 3})

    def test_post_filter_can_come_back_short(self):
        pre = self.idx.search(self.s, T, k=1, filter="pre")
        post = self.idx.search(self.s, T, k=1, filter="post")
        self.assertEqual(len(pre), 1)
        self.assertEqual(post, [])          # the best text match is not open to grade 10

    def test_matched_terms_and_days_left(self):
        r = self.idx.search(self.s, T)[0]
        self.assertEqual(r.matched, ["autonomous", "robot"])
        self.assertEqual(r.days_left, (dt.date(2099, 1, 1) - T).days)

    def test_no_match_returns_nothing(self):
        self.assertEqual(self.idx.search(Student(10, "IL", "underwater basket weaving"), T), [])

    def test_empty_catalog(self):
        self.assertEqual(Index([]).search(self.s, T), [])

    def test_why_not(self):
        self.assertEqual(self.idx.why_not(self.s, T), {"grade": 1, "deadline passed": 1})

    def test_title_outweighs_body(self):
        idx = Index([opp(0, "Chemistry Program", "students apply summer"), opp(1, "Summer Program", "chemistry students apply")])
        self.assertEqual(idx.search(Student(10, "IL", "chemistry"), T)[0].opp.id, 0)

    def test_expansion_adds_terms_but_keeps_rules(self):
        res = self.idx.search(self.s, T, expand=3)
        self.assertTrue(all(not check(r.opp, self.s, T) for r in res))
        self.assertEqual(res[0].opp.id, 0)


class Synthetic(unittest.TestCase):
    def test_deterministic(self):
        self.assertEqual(catalog(50, T, seed=5), catalog(50, T, seed=5))
        self.assertEqual(students(5, seed=5)[0][0], students(5, seed=5)[0][0])

    def test_search_never_reads_topic_labels(self):
        a = catalog(300, T, seed=1)
        b = catalog(300, T, seed=1)
        for o in b:
            o.topics = ()
        for s, _ in students(20, seed=9):
            self.assertEqual([r.opp.id for r in Index(a).search(s, T)], [r.opp.id for r in Index(b).search(s, T)])

    def test_pre_filter_results_always_eligible(self):
        idx = Index(catalog(500, T, seed=3))
        for s, _ in students(50, seed=4):
            for r in idx.search(s, T):
                self.assertEqual(check(r.opp, s, T), [])
                self.assertGreaterEqual(r.days_left, 0)


if __name__ == "__main__":
    unittest.main()
