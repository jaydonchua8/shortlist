"""Two more sets of listing wordings that extract.py was not developed against. All synthetic.

Set A (HeldoutPhrases, seed 101): written after the first version of extract.py was frozen. That
version got 54.2% of set A listings fully right (recorded in round1_results.json). I then read
the failures and fixed five causes in extract.py, so set A is now a development set and its
current score says nothing about new wordings.

Set B (FreshPhrases, seed 303): written after those fixes, with extract.py frozen again. I ran
it once and did not change extract.py afterwards. This is the number to trust.

Both sets were written by me, the same person who wrote the extractor, so they are closer to
what the extractor expects than real listings would be. Each set also uses a different seed and
different rule rates than the tuning catalog in gen.py.
"""
import datetime as dt
from gen import MON, MONTH, PLURAL, STATE_NAME, Phrases, join, text_catalog

ORD = {9: "9th", 10: "10th", 11: "11th", 12: "12th"}
WORD = {9: "ninth", 10: "tenth", 11: "eleventh", 12: "twelfth"}
SING = {9: "freshman", 10: "sophomore", 11: "junior", 12: "senior"}


class HeldoutPhrases(Phrases):
    def __init__(self, today):
        # graduation year of a student in grade g during the school year that contains `today`
        end = today.year + (1 if today.month >= 7 else 0)
        self.class_of = {g: end + (12 - g) for g in (9, 10, 11, 12)}

    def grade(self, g, rng):
        lo, hi = g[0], g[-1]
        opts = ["We accept %s graders." % join(ORD[x] for x in g),
                "You must be in the Class of %s to apply." % " or ".join(str(self.class_of[x]) for x in reversed(g))]
        if lo < hi:
            opts.append("This opportunity is for %s through %s." % (PLURAL[lo], PLURAL[hi]))
            opts.append("Students currently in %s through %s grade are eligible." % (WORD[lo], WORD[hi]))
        else:
            opts.append("You must be a current %s." % SING[lo])
        if hi == 12 and lo > 9:
            opts.append("You must be at least a %s in high school." % SING[lo])
        if hi <= 11:
            opts.append("For students entering grades %s in the fall." %
                        ("%d-%d" % (lo + 1, hi + 1) if lo < hi else str(lo + 1)))
        if lo > 9 and hi == 12:
            opts.append("Any high schooler can apply, except %s." % join(PLURAL[x] for x in range(9, lo)))
        if (lo, hi) == (9, 12):
            opts.append("Any student enrolled in high school can apply.")
        return rng.choice(opts)

    def state(self, st, rng):
        if not st:
            return rng.choice(["", "", "Students anywhere in the country can apply.",
                               "We take applicants from all 50 states."])
        return rng.choice(["You must live in %s." % " or ".join(STATE_NAME[x] for x in st),
                           "Limited to %s residents." % join(STATE_NAME[x] for x in st),
                           "Eligible applicants are enrolled in a %s high school." % " or ".join(STATE_NAME[x] for x in st),
                           "Residency in %s is required." % " or ".join(st)])

    def citizen(self, c, rng):
        if c:
            return rng.choice(["Only citizens of the United States and green card holders are eligible.",
                               "Proof of U.S. citizenship or permanent residency will be requested.",
                               "This award is restricted to American citizens."])
        return rng.choice(["", "", "", "You do not need to be a U.S. citizen.",
                           "We welcome applicants regardless of immigration status."])

    def cost(self, c, rng):
        if c == 0:
            return rng.choice(["Admitted students attend at no charge.",
                               "It costs nothing to take part.",
                               "This is a paid position at $%d per hour." % rng.choice([15, 18, 22]),
                               "There are no fees of any kind.",
                               "All expenses are covered by our sponsors."])
        opts = ["Families pay $%s for the full session." % format(c, ","),
                "Cost: $%s (some fee waivers are offered)." % format(c, ","),
                "Participation costs %s dollars." % format(c, ","),
                "The $%s tuition includes housing and meals." % format(c, ",")]
        if c >= 1000 and c % 500 == 0:
            opts.append("Tuition is $%gk, and aid can cover up to $%gk of it." % (c / 1000, c / 2000))
        if c > 100:
            opts.append("A $25 fee is due with the application, and enrolled students pay $%s." % format(c - 25, ","))
        return rng.choice(opts)

    def deadline(self, d, posted, rng):
        suffix = "th" if 10 <= d.day % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(d.day % 10, "th")
        start = d + dt.timedelta(days=75)
        return rng.choice([
            "Submit your application no later than %d %s %d." % (d.day, MONTH[d.month - 1], d.year),
            "Deadline: %s. %d%s." % (MON[d.month - 1], d.day, suffix),
            "All materials must be received by %s." % d.isoformat(),
            "The form closes on %02d/%02d/%s." % (d.month, d.day, str(d.year)[2:]),
            "The session starts %s %d, and applications are due %s %d." % (
                MONTH[start.month - 1], start.day, MONTH[d.month - 1], d.day),
            "%s %d, %d is the last day to apply." % (MONTH[d.month - 1], d.day, d.year)])

    def extras(self, o, d, rng):
        notify = d + dt.timedelta(days=21)
        out = ["Last year's cohort included students from Texas, Ohio and Florida.",
               "Mentors include college juniors and seniors from partner universities.",
               "Finalists are notified by %s %d." % (MONTH[notify.month - 1], notify.day),
               "An info session will be held on %s %d." % (MON[(d.month - 3) % 12], 12),
               "Alumni have earned more than $2 million in college scholarships.",
               "Free parking is available on site.",
               "The grand prize is $%s." % format(rng.choice([1000, 5000, 10000]), ","),
               "We received 1,200 applications for 60 spots in 2025.",
               "Our office is in Columbus, OH."]
        return rng.sample(out, rng.randint(1, 3))


class FreshPhrases(HeldoutPhrases):
    def grade(self, g, rng):
        lo, hi = g[0], g[-1]
        opts = ["Eligibility is limited to %s." % join(PLURAL[x] for x in g),
                "Current %s graders may apply." % ("%s-%s" % (ORD[lo], ORD[hi]) if lo < hi else ORD[lo]),
                "Students graduating in %s are eligible." % " or ".join(str(self.class_of[x]) for x in reversed(g)),
                "%s year students are welcome." % join(SING[x] for x in g).capitalize()]
        if hi == 12:
            opts.append("Applicants should be in grade %d or higher." % lo)
        if hi <= 11:
            opts.append("Open to rising %s graders." % join(ORD[x + 1] for x in g))
        if lo > 9 and hi == 12:
            opts.append("This program is for high school students. %s may not apply."
                        % join(PLURAL[x] for x in range(9, lo)).capitalize())
        return rng.choice(opts)

    def state(self, st, rng):
        if not st:
            return rng.choice(["", "", "Open to U.S. students in any state.",
                               "Applicants may live anywhere in the United States."])
        return rng.choice(["Applicants must attend a high school in %s." % " or ".join(STATE_NAME[x] for x in st),
                           "Open only to students residing in %s." % " or ".join(STATE_NAME[x] for x in st),
                           "%s students only." % join(STATE_NAME[x] for x in st),
                           "Must be a resident of %s." % " or ".join(st)])

    def citizen(self, c, rng):
        if c:
            return rng.choice(["Applicants must hold U.S. citizenship.",
                               "Open to U.S. citizens and lawful permanent residents only.",
                               "You must be a citizen or permanent resident of the United States."])
        return rng.choice(["", "", "", "Citizenship status does not affect eligibility.",
                           "Non-citizens may apply."])

    def cost(self, c, rng):
        if c == 0:
            return rng.choice(["There is no tuition.", "Students pay nothing to attend.",
                               "Free for all accepted students.",
                               "Interns are paid a stipend of $%s." % format(rng.choice([800, 1200, 2400]), ","),
                               "No program fee is charged."])
        opts = ["Program cost: $%s." % format(c, ","),
                "The fee for the %d-week session is $%s." % (rng.choice([2, 4, 6]), format(c, ",")),
                "Expect to pay about $%s in tuition." % format(c, ","),
                "$%s per student, with a limited number of full scholarships." % format(c, ",")]
        if c > 100:
            opts.append("Tuition: $%s. Application fee: $40 (waived on request)." % format(c - 40, ","))
        return rng.choice(opts)

    def deadline(self, d, posted, rng):
        suffix = "th" if 10 <= d.day % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(d.day % 10, "th")
        later = d + dt.timedelta(days=28)
        return rng.choice([
            "Applications close %s %d, %d." % (MONTH[d.month - 1], d.day, d.year),
            "Due date: %d/%d/%d." % (d.month, d.day, d.year),
            "Apply on or before %s %d." % (MONTH[d.month - 1], d.day),
            "The deadline to apply is the %d%s of %s." % (d.day, suffix, MONTH[d.month - 1]),
            "Submissions are accepted through %s %d, %d; winners are announced %s %d." % (
                MONTH[d.month - 1], d.day, d.year, MONTH[later.month - 1], later.day),
            "Registration ends %s %d, %d." % (MONTH[d.month - 1], d.day, d.year)])

    def extras(self, o, d, rng):
        week = d + dt.timedelta(days=14)
        out = ["Participants meet twice a week from 4 to 6 pm.",
               "The 2025 cohort had 48 students from 9 states.",
               "Many alumni now attend universities in California and New York.",
               "Our instructors are seniors at the university.",
               "A $200 travel grant is available to students who need it.",
               "Breakfast and lunch are free.",
               "Classes meet in Atlanta, GA.",
               "Interviews take place the week of %s %d." % (MONTH[week.month - 1], week.day),
               "The winning team earned $10,000 last year.",
               "Students living in rural areas are encouraged to apply."]
        return rng.sample(out, rng.randint(1, 3))


def fresh_catalog(n, today, seed=303):
    return text_catalog(n, today, seed, phrases=FreshPhrases(today),
                        p_omit={"grade": 0.12, "cost": 0.10, "deadline": 0.10},
                        p_state=0.5, p_free=0.45, p_citizen=0.25)


def heldout_catalog(n, today, seed=101):
    return text_catalog(n, today, seed, phrases=HeldoutPhrases(today),
                        p_omit={"grade": 0.15, "cost": 0.15, "deadline": 0.12},
                        p_state=0.35, p_free=0.4, p_citizen=0.3)
