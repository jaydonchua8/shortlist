"""shortlist: rank a catalog of opportunities for one student, eligible ones only.

Two parts:
  check(opp, student, today)  hard rules. Returns the reasons a student cannot apply (empty = can).
  Index(opps).search(...)     BM25 over title and description, restricted to opportunities that pass check.

An Opportunity can name fields in `unknown` when its rules were read from free text (see extract.py)
and the text did not state them. An unknown field never excludes a listing in check; search either
shows such listings with a `verify` flag or hides them, depending on the `unknown` argument.

Standard library only.
"""
import datetime as dt
import math
import re
from functools import lru_cache
from collections import Counter, defaultdict
from dataclasses import dataclass, field

STOP = set("a an and are as at be by for from i in interested is it like me my of on or "
           "that the to want with about also am into love enjoy".split())


def tokens(text):
    out = []
    for w in re.findall(r"[a-z0-9]+", text.lower()):
        if w in STOP:
            continue
        if len(w) > 3 and w.endswith("s") and not w.endswith(("ss", "us")):
            w = w[:-1]
        out.append(w)
    return out


@dataclass
class Opportunity:
    id: int
    title: str
    text: str
    kind: str = "program"
    grades: tuple = (9, 10, 11, 12)
    states: tuple = ()            # empty means open to any state
    citizens_only: bool = False
    cost: int = 0
    deadline: str = "2099-01-01"  # ISO date, last day to apply
    topics: tuple = ()            # only used by the benchmark as ground truth, never by search
    unknown: tuple = ()           # any of "grade", "cost", "deadline": not stated in the listing


@dataclass
class Student:
    grade: int
    state: str
    interests: str
    citizen: bool = True
    budget: int = 0


@dataclass
class Result:
    opp: Opportunity
    score: float
    matched: list = field(default_factory=list)
    days_left: int = 0
    verify: tuple = ()            # fields the student should confirm on the listing itself


@lru_cache(maxsize=None)
def _date(iso):
    return dt.date.fromisoformat(iso)


def check(opp, student, today):
    """Return a list of reasons the student cannot apply. Empty list means eligible."""
    why = []
    unk = opp.unknown
    if "deadline" not in unk and _date(opp.deadline) < today:
        why.append("deadline passed")
    if "grade" not in unk and student.grade not in opp.grades:
        why.append("grade")
    if opp.states and student.state not in opp.states:
        why.append("state")
    if opp.citizens_only and not student.citizen:
        why.append("citizenship")
    if "cost" not in unk and opp.cost > student.budget:
        why.append("cost")
    return why


class Index:
    TITLE_WEIGHT = 2      # a title term counts as this many description terms
    K1, B = 1.2, 0.75

    def __init__(self, opps):
        self.opps = list(opps)
        self.post = defaultdict(list)          # term -> [(doc index, weighted tf)]
        self.length = []
        for i, o in enumerate(self.opps):
            tf = Counter(tokens(o.text))
            for t in tokens(o.title):
                tf[t] += self.TITLE_WEIGHT
            self.length.append(sum(tf.values()))
            for t, f in tf.items():
                self.post[t].append((i, f))
        n = len(self.opps)
        self.avg = (sum(self.length) / n) if n else 1.0
        self.idf = {t: math.log(1 + (n - len(p) + 0.5) / (len(p) + 0.5)) for t, p in self.post.items()}

    def _score(self, weights):
        """weights: term -> query weight. Returns (scores by doc index, matched terms by doc index)."""
        scores, matched = defaultdict(float), defaultdict(list)
        for t, w in weights.items():
            idf = self.idf.get(t)
            if idf is None:
                continue
            for i, f in self.post[t]:
                norm = f + self.K1 * (1 - self.B + self.B * self.length[i] / self.avg)
                scores[i] += w * idf * f * (self.K1 + 1) / norm
                matched[i].append(t)
        return scores, matched

    def _top(self, scores, matched, allowed, k, today):
        """allowed: None, or a function of the doc index. It is only called while walking down the
        ranking, so a query stops checking rules once it has k results."""
        ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
        out = []
        for i, s in ranked:
            if allowed is not None and not allowed(i):
                continue
            o = self.opps[i]
            days = (_date(o.deadline) - today).days
            out.append(Result(o, round(s, 4), sorted(matched[i]), days, tuple(o.unknown)))
            if len(out) == k:
                break
        return out

    def _allowed(self, student, today, unknown):
        if unknown not in ("show", "hide"):
            raise ValueError("unknown must be 'show' or 'hide'")
        hide = unknown == "hide"
        return lambda i: not (hide and self.opps[i].unknown) and not check(self.opps[i], student, today)

    def eligible(self, student, today, unknown="show"):
        ok = self._allowed(student, today, unknown)
        return {i for i in range(len(self.opps)) if ok(i)}

    def search(self, student, today, k=10, filter="pre", expand=0, unknown="show"):
        """filter: "pre"  rank only eligible opportunities (default)
                   "post" take the top k by text score, then drop ineligible ones
                   "none" ignore eligibility
        expand: if > 0, add this many terms taken from the top 5 eligible results and search again.
        unknown: "show" keeps listings with unstated fields and flags them in Result.verify
                 "hide" drops any listing with an unstated field"""
        if filter not in ("pre", "post", "none"):
            raise ValueError("filter must be 'pre', 'post' or 'none'")
        weights = {t: 1.0 for t in set(tokens(student.interests))}
        scores, matched = self._score(weights)
        allowed = self._allowed(student, today, unknown) if filter != "none" else None
        if expand and filter == "pre":
            first = self._top(scores, matched, allowed, 5, today)
            pool = Counter()
            for r in first:
                for t in set(tokens(r.opp.title + " " + r.opp.text)):
                    if t not in weights:
                        pool[t] += self.idf.get(t, 0.0)
            for t, _ in sorted(pool.items(), key=lambda kv: (-kv[1], kv[0]))[:expand]:
                weights[t] = 0.3
            scores, matched = self._score(weights)
        if filter == "post":
            top = self._top(scores, matched, None, k, today)
            keep = {id(r) for r, i in zip(top, self._top_ids(scores, k)) if allowed(i)}
            return [r for r in top if id(r) in keep]
        return self._top(scores, matched, allowed, k, today)

    @staticmethod
    def _top_ids(scores, k):
        return [i for i, _ in sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[:k]]

    def why_not(self, student, today):
        """Count how many opportunities each rule removes for this student."""
        c = Counter()
        for o in self.opps:
            for reason in check(o, student, today):
                c[reason] += 1
        return dict(c)


if __name__ == "__main__":
    import sys
    from gen import catalog, students
    today = dt.date(2026, 11, 1)
    idx = Index(catalog(3000, today, seed=1))
    s = students(1, seed=int(sys.argv[1]) if len(sys.argv) > 1 else 3)[0][0]
    print("student: grade %d, %s, citizen=%s, budget $%d" % (s.grade, s.state, s.citizen, s.budget))
    print("interests:", s.interests)
    print("eligible: %d of %d" % (len(idx.eligible(s, today)), len(idx.opps)))
    print("removed by rule:", idx.why_not(s, today))
    for r in idx.search(s, today, k=5):
        print("  %6.2f  %-52s due in %3d days  matched: %s" % (r.score, r.opp.title[:52], r.days_left, ", ".join(r.matched)))
