"""Synthetic catalog and student profiles with known ground truth. All data here is made up.

Each opportunity is written from one or two topics, and a quarter of them also mention
two words from an unrelated topic in passing. Each student is interested in two topics.
An opportunity is "relevant" to a student when it shares a topic and the student is eligible.
The topic labels are stored for scoring the benchmark and are never read by the search code.

text_catalog() additionally writes each listing's rules out as an English eligibility paragraph
(grade, state, citizenship, cost, deadline) mixed with sentences that mention grades, dollar
amounts and dates that are NOT rules. extract.py was developed against the phrasings in this
file. heldout.py has a second set of phrasings that it was not developed against.
"""
import datetime as dt
import random
from collections import namedtuple
from shortlist import Opportunity, Student

TOPICS = {
    "robotics": "robotics robot mechatronics actuator sensor autonomous drone arduino controller mechanical",
    "software": "programming software coding algorithm python developer hackathon app web database",
    "ai": "machine learning neural model data training artificial intelligence prediction algorithm",
    "biology": "biology genetics cell molecular laboratory organism microbiology dna ecology specimen",
    "medicine": "medicine clinical hospital patient physician health anatomy surgery shadowing diagnosis",
    "chemistry": "chemistry reaction compound laboratory synthesis organic molecule titration polymer catalyst",
    "physics": "physics quantum particle mechanics relativity optics astrophysics experiment energy theory",
    "math": "mathematics proof olympiad combinatorics geometry algebra number theory calculus contest",
    "space": "space astronomy telescope satellite rocket orbit planetary aerospace launch mission",
    "environment": "environment climate sustainability conservation ecology renewable energy wildlife pollution field",
    "writing": "writing essay fiction poetry journalism editor manuscript publication storytelling prose",
    "art": "art painting drawing portfolio studio illustration sculpture gallery design visual",
    "music": "music orchestra composition instrument performance ensemble conservatory audition choir jazz",
    "theater": "theater acting stage drama performance playwright audition directing musical production",
    "film": "film cinema video directing screenplay editing documentary animation production camera",
    "business": "business entrepreneurship startup pitch marketing venture finance product founder revenue",
    "economics": "economics market policy finance trade inflation econometrics data investing research",
    "law": "law legal court debate constitution mock trial advocacy justice policy attorney",
    "politics": "politics government policy civic congress campaign diplomacy election leadership debate",
    "history": "history archive museum civilization historical research heritage archaeology essay primary",
    "psychology": "psychology behavior cognitive brain neuroscience experiment mental research survey perception",
    "service": "volunteer community service nonprofit outreach tutoring mentoring fundraising leadership shelter",
    "languages": "language linguistics translation immersion spanish mandarin french bilingual culture exchange",
    "engineering": "engineering design prototype civil structural mechanical circuit cad build bridge",
}
TOPICS = {k: v.split() for k, v in TOPICS.items()}
FILLER = ("students program apply application selected participants weeks summer week mentor faculty project "
          "team final present opportunity high school open award stipend housing campus online session cohort "
          "learn skills experience hands work national regional annual deadline required recommendation").split()
KINDS = ["Summer Program", "Competition", "Scholarship", "Internship", "Research Program", "Fellowship"]
STATES = ["CA", "NY", "TX", "IL", "MA", "WA", "FL", "PA", "GA", "OH", "NJ", "VA"]


def catalog(n, today, seed=1, p_state=0.45, p_free=0.5, p_citizen=0.2):
    rng = random.Random(seed)
    names = list(TOPICS)
    out = []
    for i in range(n):
        tp = [rng.choice(names)]
        if rng.random() < 0.3:
            tp.append(rng.choice([t for t in names if t != tp[0]]))
        words = rng.sample(TOPICS[tp[0]], 4)
        if len(tp) == 2:
            words += rng.sample(TOPICS[tp[1]], 3)
        if rng.random() < 0.25:   # mentions another field in passing without being about it
            words += rng.sample(TOPICS[rng.choice([t for t in names if t not in tp])], 2)
        body = words + [rng.choice(FILLER) for _ in range(18)]
        rng.shuffle(body)
        kind = rng.choice(KINDS)
        title = "%s %s %s" % (rng.choice(TOPICS[tp[0]]).title(), rng.choice(FILLER).title(), kind)
        lo = rng.randint(9, 12)
        hi = rng.randint(lo, 12)
        states = tuple(rng.sample(STATES, rng.randint(1, 3))) if rng.random() < p_state else ()
        cost = 0 if rng.random() < p_free else rng.choice([50, 150, 400, 900, 1800, 3500, 6000])
        deadline = today + dt.timedelta(days=rng.randint(-60, 240))
        out.append(Opportunity(i, title, " ".join(body), kind, tuple(range(lo, hi + 1)), states,
                               rng.random() < p_citizen, cost, deadline.isoformat(), tuple(tp)))
    return out


def students(n, seed=2):
    """Returns [(Student, set of interest topics)]."""
    rng = random.Random(seed)
    names = list(TOPICS)
    out = []
    for _ in range(n):
        tp = rng.sample(names, 2)
        words = rng.sample(TOPICS[tp[0]], 2) + rng.sample(TOPICS[tp[1]], 2) + rng.sample(FILLER, 4)
        rng.shuffle(words)
        s = Student(rng.randint(9, 12), rng.choice(STATES), "I am interested in " + " ".join(words),
                    rng.random() < 0.85, rng.choice([0, 500, 2000, 10000]))
        out.append((s, set(tp)))
    return out


# ---------------------------------------------------------------- listings as free text

STATE_NAME = {"CA": "California", "NY": "New York", "TX": "Texas", "IL": "Illinois", "MA": "Massachusetts",
              "WA": "Washington", "FL": "Florida", "PA": "Pennsylvania", "GA": "Georgia", "OH": "Ohio",
              "NJ": "New Jersey", "VA": "Virginia"}
PLURAL = {9: "freshmen", 10: "sophomores", 11: "juniors", 12: "seniors"}
MONTH = ("January February March April May June July August September October November December").split()
MON = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()

Listing = namedtuple("Listing", "truth posted omitted")   # truth: Opportunity whose text is the full listing


def join(words):
    words = list(words)
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


def long_date(d, year=True):
    return "%s %d%s" % (MONTH[d.month - 1], d.day, ", %d" % d.year if year else "")


class Phrases:
    """The wordings extract.py was written against. One method per field; each returns a sentence
    (or "" to say nothing). `extras` returns sentences that look like rules and are not."""

    def grade(self, g, rng):
        lo, hi = g[0], g[-1]
        opts = ["Open to students in grades %d-%d." % (lo, hi) if lo < hi else "Open to students in grade %d." % lo,
                "Eligibility: current %s." % join(PLURAL[x] for x in g)]
        if hi <= 11:
            opts.append("Applicants must be rising %s." % join(PLURAL[x + 1] for x in g))
        if (lo, hi) == (9, 12):
            opts.append("Open to all high school students.")
        if hi == 12 and lo > 9:
            opts.append("Students in %dth grade or above may apply." % lo)
        if (lo, hi) == (9, 11):
            opts.append("Open to high school students. Graduating seniors are not eligible.")
        return rng.choice(opts)

    def state(self, st, rng):
        if not st:
            return rng.choice(["", "", "Open to students nationwide.", "There is no residency requirement."])
        return rng.choice(["Applicants must be residents of %s." % join(STATE_NAME[x] for x in st),
                           "Open to students who attend school in %s." % join(st),
                           "Only %s residents may apply." % " or ".join(STATE_NAME[x] for x in st)])

    def citizen(self, c, rng):
        if c:
            return rng.choice(["Applicants must be US citizens or permanent residents.",
                               "U.S. citizenship is required."])
        return rng.choice(["", "", "", "International students are welcome to apply.",
                           "US citizenship is not required."])

    def cost(self, c, rng):
        if c == 0:
            return rng.choice(["The program is free to attend.", "There is no cost to participate.",
                               "Participants receive a $%s stipend." % format(rng.choice([500, 1000, 1500, 3000]), ","),
                               "Fully funded: tuition, housing and meals are covered."])
        opts = ["Tuition is $%s." % format(c, ","), "The program fee is $%s." % format(c, ","),
                "The cost to attend is $%s. Need-based scholarships of up to $%s are available."
                % (format(c, ","), format(rng.choice([250, 1000, 2000, 5000]), ","))]
        if c > 100:
            opts.append("Tuition is $%s and there is a $50 application fee." % format(c - 50, ","))
        return rng.choice(opts)

    def deadline(self, d, posted, rng):
        early = d - dt.timedelta(days=30)
        return rng.choice([
            "Applications are due %s." % long_date(d),
            "The application deadline is %s." % long_date(d, year=False),
            "Apply by %d/%d/%d." % (d.month, d.day, d.year),
            "Applications open %s and close %s." % (long_date(posted - dt.timedelta(days=10), False), long_date(d)),
            "Priority deadline %s %d; final deadline %s %d, %d." % (MON[early.month - 1], early.day,
                                                                    MON[d.month - 1], d.day, d.year)])

    def extras(self, o, d, rng):
        start = d + dt.timedelta(days=rng.randint(60, 120))
        out = ["Sessions are led by senior researchers and junior faculty.",
               "Each cohort is capped at %d students." % rng.choice([12, 20, 40]),
               "Founded in %d, the program has hosted students from %d states." % (rng.randint(1985, 2019), rng.randint(9, 40)),
               "The program runs from %s to %s." % (long_date(start, False), long_date(start + dt.timedelta(days=41))),
               "Decisions are released on %s." % long_date(d + dt.timedelta(days=30), False),
               "Held on campus in %s." % rng.choice(["Austin, TX", "Boston, MA", "Chicago, IL", "Seattle, WA"]),
               "Lunch is free on program days.",
               "Top teams receive a $%s prize." % format(rng.choice([500, 1000, 2500]), ",")]
        return rng.sample(out, rng.randint(1, 3))


def render(o, posted, rng, phrases, p_omit):
    """Returns (listing text, set of fields left out of the text)."""
    d = dt.date.fromisoformat(o.deadline)
    omitted = {f for f in ("grade", "cost", "deadline") if rng.random() < p_omit[f]}
    parts = [phrases.state(o.states, rng), phrases.citizen(o.citizens_only, rng)]
    if "grade" not in omitted:
        parts.append(phrases.grade(o.grades, rng))
    if "cost" not in omitted:
        parts.append(phrases.cost(o.cost, rng))
    if "deadline" not in omitted:
        parts.append(phrases.deadline(d, posted, rng))
    parts += phrases.extras(o, d, rng)
    parts = [p for p in parts if p]
    rng.shuffle(parts)
    return o.text.capitalize() + ". " + " ".join(parts), omitted


def text_catalog(n, today, seed=1, phrases=None, p_omit=None, **rates):
    """Synthetic listings whose rules are only available as English text.
    Each listing has a collection date 45 to 200 days before its deadline."""
    import dataclasses
    phrases = phrases or Phrases()
    p_omit = p_omit or {"grade": 0.10, "cost": 0.12, "deadline": 0.08}
    rng = random.Random(seed * 7919 + 13)
    out = []
    for o in catalog(n, today, seed, **rates):
        posted = dt.date.fromisoformat(o.deadline) - dt.timedelta(days=rng.randint(45, 200))
        text, omitted = render(o, posted, rng, phrases, p_omit)
        out.append(Listing(dataclasses.replace(o, text=text), posted, frozenset(omitted)))
    return out
