import datetime as dt
import io
import unittest
from contextlib import redirect_stdout

import bench
from extract import Extracted, extract, sentences, to_opportunity
from gen import students, text_catalog
from heldout import fresh_catalog, heldout_catalog
from shortlist import Index, Student, check

T = dt.date(2026, 11, 1)


def x(text, as_of=T, today=None):
    return extract(text, as_of, today)


class Grade(unittest.TestCase):
    def g(self, text, **kw):
        r = x(text, **kw)
        return None if "grade" in r.unknown else r.grades

    def test_range_and_list(self):
        self.assertEqual(self.g("Open to students in grades 10-12."), (10, 11, 12))
        self.assertEqual(self.g("Eligibility: current sophomores and juniors."), (10, 11))
        self.assertEqual(self.g("We accept 9th, 10th and 11th graders."), (9, 10, 11))
        self.assertEqual(self.g("Students currently in tenth through twelfth grade are eligible."), (10, 11, 12))

    def test_rising_means_one_grade_lower_today(self):
        self.assertEqual(self.g("Applicants must be rising juniors and seniors."), (10, 11))
        self.assertEqual(self.g("For students entering grades 10-12 in the fall."), (9, 10, 11))

    def test_rising_freshmen_are_not_in_high_school_yet(self):
        self.assertIsNone(self.g("Applicants must be rising freshmen."))

    def test_open_ended(self):
        self.assertEqual(self.g("Students in 10th grade or above may apply."), (10, 11, 12))
        self.assertEqual(self.g("You must be at least a junior in high school."), (11, 12))

    def test_negation_removes_grades(self):
        self.assertEqual(self.g("Open to high school students. Graduating seniors are not eligible."), (9, 10, 11))
        self.assertEqual(self.g("Any high schooler can apply, except freshmen and sophomores."), (11, 12))

    def test_all_high_school(self):
        self.assertEqual(self.g("Open to all high school students."), (9, 10, 11, 12))

    def test_job_titles_and_college_years_are_not_grades(self):
        self.assertIsNone(self.g("Sessions are led by senior researchers and junior faculty."))
        self.assertIsNone(self.g("Mentors include college juniors and seniors from partner universities."))
        self.assertIsNone(self.g("Each cohort is capped at 12 students."))

    def test_class_of_depends_on_the_query_date_not_the_collection_date(self):
        text = "You must be in the Class of 2028 to apply."
        self.assertEqual(self.g(text, as_of=dt.date(2026, 5, 1), today=dt.date(2026, 11, 1)), (11,))
        self.assertEqual(self.g(text, as_of=dt.date(2026, 5, 1), today=dt.date(2027, 9, 1)), (12,))
        self.assertIsNone(self.g("You must be in the Class of 2035 to apply."))

    def test_not_stated_is_unknown(self):
        self.assertIsNone(self.g("A robotics program with a final project."))


class StateAndCitizenship(unittest.TestCase):
    def test_names_and_abbreviations(self):
        self.assertEqual(x("Applicants must be residents of Illinois and New York.").states, ("IL", "NY"))
        self.assertEqual(x("Open to students who attend school in CA, WA and TX.").states, ("CA", "TX", "WA"))
        self.assertEqual(x("Only West Virginia residents may apply.").states, ("WV",))

    def test_location_and_history_are_not_residency(self):
        self.assertEqual(x("Held on campus in Austin, TX.").states, ())
        self.assertEqual(x("Last year's cohort included students from Texas, Ohio and Florida.").states, ())

    def test_nationwide(self):
        self.assertEqual(x("We take applicants from all 50 states.").states, ())

    def test_citizenship(self):
        self.assertTrue(x("Applicants must be US citizens or permanent residents.").citizens_only)
        self.assertTrue(x("U.S. citizenship is required.").citizens_only)
        self.assertFalse(x("US citizenship is not required.").citizens_only)
        self.assertFalse(x("You do not need to be a U.S. citizen.").citizens_only)
        self.assertFalse(x("International students are welcome to apply.").citizens_only)
        self.assertFalse(x("A robotics program.").citizens_only)


class Cost(unittest.TestCase):
    def c(self, text):
        r = x(text)
        return None if "cost" in r.unknown else r.cost

    def test_amounts(self):
        self.assertEqual(self.c("Tuition is $3,500."), 3500)
        self.assertEqual(self.c("Participation costs 900 dollars."), 900)
        self.assertEqual(self.c("Tuition is $3.5k, and aid can cover up to $1.75k of it."), 3500)

    def test_application_fee_is_added(self):
        self.assertEqual(self.c("Tuition is $3,450 and there is a $50 application fee."), 3500)
        self.assertEqual(self.c("A $25 fee is due with the application, and enrolled students pay $875."), 900)

    def test_free(self):
        self.assertEqual(self.c("The program is free to attend."), 0)
        self.assertEqual(self.c("Fully funded: tuition, housing and meals are covered."), 0)
        self.assertEqual(self.c("All expenses are covered by our sponsors."), 0)

    def test_money_paid_to_the_student_is_not_a_cost(self):
        self.assertEqual(self.c("Participants receive a $1,500 stipend."), 0)
        self.assertEqual(self.c("This is a paid position at $18 per hour."), 0)

    def test_aid_and_prizes_do_not_set_the_cost(self):
        self.assertEqual(self.c("The cost to attend is $900. Need-based scholarships of up to $2,000 are available."), 900)
        self.assertIsNone(self.c("Top teams receive a $2,500 prize."))
        self.assertIsNone(self.c("Alumni have earned more than $2 million in college scholarships."))

    def test_free_lunch_is_not_a_free_program(self):
        self.assertIsNone(self.c("Lunch is free on program days."))
        self.assertIsNone(self.c("Free parking is available on site."))

    def test_not_stated_is_unknown(self):
        self.assertIsNone(self.c("Open to students in grades 10-12."))


class Deadline(unittest.TestCase):
    def d(self, text, as_of=T):
        r = x(text, as_of)
        return None if "deadline" in r.unknown else r.deadline

    def test_formats(self):
        self.assertEqual(self.d("Applications are due March 1, 2027."), "2027-03-01")
        self.assertEqual(self.d("Apply by 3/1/2027."), "2027-03-01")
        self.assertEqual(self.d("The form closes on 03/01/27."), "2027-03-01")
        self.assertEqual(self.d("All materials must be received by 2027-03-01."), "2027-03-01")
        self.assertEqual(self.d("Submit your application no later than 1 March 2027."), "2027-03-01")
        self.assertEqual(self.d("Deadline: Mar. 3rd."), "2027-03-03")
        self.assertEqual(self.d("Deadline: May. 3rd."), "2027-05-03")

    def test_missing_year_is_the_next_occurrence_after_collection(self):
        text = "The application deadline is March 1."
        self.assertEqual(self.d(text, dt.date(2026, 11, 1)), "2027-03-01")
        self.assertEqual(self.d(text, dt.date(2027, 2, 1)), "2027-03-01")
        self.assertEqual(self.d(text, dt.date(2027, 3, 1)), "2027-03-01")
        self.assertEqual(self.d(text, dt.date(2027, 3, 2)), "2028-03-01")
        self.assertIn("deadline year inferred from collection date", x(text).notes)

    def test_later_of_priority_and_final(self):
        self.assertEqual(self.d("Priority deadline Jan 15; final deadline Feb 14, 2027."), "2027-02-14")

    def test_open_date_is_not_the_deadline(self):
        self.assertEqual(self.d("Applications open October 20 and close February 1, 2027."), "2027-02-01")
        self.assertEqual(self.d("The session starts June 20, and applications are due March 1."), "2027-03-01")

    def test_other_dates_are_ignored(self):
        self.assertIsNone(self.d("The program runs from June 14 to July 25, 2027."))
        self.assertIsNone(self.d("Decisions are released on April 10."))
        self.assertIsNone(self.d("Founded in 2009, the program has hosted students from 11 states."))

    def test_impossible_date_is_unknown_not_a_crash(self):
        self.assertIsNone(self.d("Applications are due February 30, 2027."))
        self.assertIsNone(self.d("Apply by 13/45/2027."))

    def test_rolling(self):
        self.assertEqual(self.d("Applications are reviewed on a rolling basis."), "2099-01-01")

    def test_known_gap_abstains_instead_of_guessing(self):
        # A wording from held-out set B that extract.py does not understand. It should say unknown.
        self.assertIsNone(self.d("Registration ends March 1, 2027."))


class Whole(unittest.TestCase):
    def test_empty_and_junk_input(self):
        for text in ("", "   ", "?!.;", "$", "Class of", "grades", "12/", "\n\n"):
            r = x(text)
            self.assertEqual(set(r.unknown), {"grade", "cost", "deadline"}, text)
            self.assertEqual((r.states, r.citizens_only), ((), False))

    def test_long_input_finishes(self):
        r = x("Open to juniors. " + "Students learn skills on campus. " * 5000 + "Tuition is $100.")
        self.assertEqual((r.grades, r.cost), ((11,), 100))

    def test_evidence_is_the_source_sentence(self):
        r = x("A summer lab. Tuition is $900. Applications are due March 1, 2027. Open to juniors.")
        self.assertEqual(r.evidence["cost"], "Tuition is $900.")
        self.assertEqual(r.evidence["deadline"], "Applications are due March 1, 2027.")
        self.assertNotIn("state", r.evidence)

    def test_sentence_split_keeps_abbreviations_together(self):
        self.assertEqual(sentences("U.S. citizenship is required. Deadline: Mar. 3rd."),
                         ["US citizenship is required.", "Deadline: Mar 3rd."])

    def test_to_opportunity_and_search_policies(self):
        opps = [
            to_opportunity(0, "Robotics Lab", "Build a robot. Open to juniors. Tuition is $100. Apply by 3/1/2027.", T),
            to_opportunity(1, "Robotics Camp", "Build a robot with a team. Open to juniors.", T),
            to_opportunity(2, "Robotics Cup", "Robot contest. Open to seniors. Free to enter. Apply by 3/1/2027.", T),
        ]
        self.assertEqual(opps[1].unknown, ("cost", "deadline"))
        idx = Index(opps)
        s = Student(grade=11, state="IL", interests="robot", budget=500)
        shown = idx.search(s, T)
        self.assertEqual({r.opp.id for r in shown}, {0, 1})
        self.assertEqual({r.opp.id: r.verify for r in shown}, {0: (), 1: ("cost", "deadline")})
        self.assertEqual([r.opp.id for r in idx.search(s, T, unknown="hide")], [0])
        self.assertEqual(idx.eligible(s, T, "hide"), {0})
        with self.assertRaises(ValueError):
            idx.search(s, T, unknown="maybe")
        with self.assertRaises(ValueError):
            idx.search(s, T, filter="sometimes")

    def test_unknown_field_never_excludes_in_check(self):
        o = to_opportunity(0, "x", "Open to seniors.", T)
        broke = Student(grade=12, state="IL", interests="x", budget=0)
        self.assertEqual(check(o, broke, dt.date(2090, 1, 1)), [])
        self.assertEqual(check(o, Student(9, "IL", "x"), T), ["grade"])


class Data(unittest.TestCase):
    def test_text_catalog_is_deterministic_and_omits_what_it_says(self):
        a, b = text_catalog(80, T, seed=4), text_catalog(80, T, seed=4)
        self.assertEqual(a, b)
        for l in a:
            if "cost" in l.omitted:
                self.assertNotIn("uition", l.truth.text)
            self.assertLess(l.posted, dt.date.fromisoformat(l.truth.deadline))

    def test_three_sets_use_different_wordings(self):
        tails = []
        for cat in (text_catalog(200, T, seed=1), heldout_catalog(200, T), fresh_catalog(200, T)):
            tails.append({s for l in cat for s in sentences(l.truth.text)[1:]})
        self.assertFalse(tails[0] & tails[1])
        self.assertFalse(tails[0] & tails[2])
        self.assertFalse(tails[1] & tails[2])

    def test_extractor_never_reads_truth_fields(self):
        for l in text_catalog(100, T, seed=6):
            o = l.truth
            a = to_opportunity(o.id, o.title, o.text, l.posted, o.kind, T)
            self.assertEqual(a.topics, ())
            self.assertEqual(a, to_opportunity(o.id, o.title, o.text, l.posted, o.kind, T))

    def test_tuning_set_is_fully_parsed(self):
        cat = text_catalog(300, T, seed=1)
        xs = [extract(l.truth.text, l.posted, T) for l in cat]
        self.assertEqual(bench.all_fields_right(cat, xs), 100.0)

    def test_bench_scores_a_plugged_in_extractor(self):
        cat, studs = text_catalog(120, T, seed=8), students(8, seed=9)
        with redirect_stdout(io.StringIO()):
            out = bench.run("t", cat, studs,
                            extractor=lambda text, as_of, today: Extracted(unknown=("grade", "cost", "deadline")))
        f = out["fields"]
        self.assertEqual((f["grade"]["correct"], f["cost"]["wrong"], f["deadline"]["invented"]), (0, 0, 0))
        self.assertEqual(f["cost"]["missed"], f["cost"]["stated"])
        self.assertEqual(out["methods"]["extract.py, hide unknown"]["shown"], 0.0)
        self.assertEqual(out["methods"]["hand-labelled rules (ceiling)"]["ineligible_per_10"], 0.0)


if __name__ == "__main__":
    unittest.main()
