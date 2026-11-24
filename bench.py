"""Benchmark: can the shortlist stay correct when the rules have to be read out of listing text?

Three synthetic catalogs of 3,000 listings, each scored with 300 student profiles:
  tuning  gen.py wordings, seed 1. extract.py was developed against these.
  set A   heldout.py HeldoutPhrases, seed 101. Held out for version 1 of extract.py (results in
          round1_results.json), then used to fix it, so it is a development set now.
  set B   heldout.py FreshPhrases, seed 303. Written after the fixes. Held out.

Part 1 scores extract.py field by field against the rules the generator wrote the text from.
Part 2 ranks with BM25 under five sources of rules and scores the top 10. A result is useful when
the student is truly eligible AND it shares one of the student's two interest topics.
"""
import datetime as dt
import json
import os
import re
import statistics
import sys
import time
from collections import Counter
from dataclasses import replace
from extract import extract
from gen import students, text_catalog
from heldout import fresh_catalog, heldout_catalog
from shortlist import Index, Opportunity, check

TODAY = dt.date(2026, 11, 1)
K = 10
FIELDS = ("grade", "state", "citizenship", "cost", "deadline")


def naive_opportunity(o, posted):
    """Baseline extractor: the obvious first attempt. First dollar amount is the cost, first
    'Month day' is the deadline, any grade word or number counts, no handling of 'rising',
    negation, stipends or dates that are not deadlines. Never reports unknown."""
    t = o.text
    names = {"freshmen": 9, "sophomore": 10, "junior": 11, "senior": 12}
    grades = {g for w, g in names.items() if w in t.lower()}
    m = re.search(r"grades? (\d+)\s*-\s*(\d+)", t)
    if m:
        grades |= set(range(int(m.group(1)), int(m.group(2)) + 1))
    grades |= {int(g) for g in re.findall(r"\b(9|10|11|12)th", t)}
    grades = tuple(sorted(g for g in grades if 9 <= g <= 12)) or (9, 10, 11, 12)
    m = re.search(r"\$([\d,]+)", t)
    cost = int(m.group(1).replace(",", "")) if m else 0
    months = "January February March April May June July August September October November December".split()
    m = re.search(r"(%s) (\d{1,2})(?:, (\d{4}))?" % "|".join(months), t)
    deadline = "2099-01-01"
    if m:
        try:
            deadline = dt.date(int(m.group(3) or posted.year), months.index(m.group(1)) + 1, int(m.group(2))).isoformat()
        except ValueError:
            pass
    states = tuple(sorted(set(re.findall(r"\b(CA|NY|TX|IL|MA|WA|FL|PA|GA|OH|NJ|VA)\b", t))))
    return replace(o, grades=grades, states=states, citizens_only="citizen" in t.lower(), cost=cost,
                   deadline=deadline, topics=())


def field_scores(listings, xs):
    """Per field: correct, wrong, and the two kinds of abstaining. xs: one Extracted per listing."""
    out = {f: Counter() for f in FIELDS}
    for l, x in zip(listings, xs):
        o = l.truth
        truth = {"grade": o.grades, "state": tuple(sorted(o.states)), "citizenship": o.citizens_only,
                 "cost": o.cost, "deadline": o.deadline}
        got = {"grade": x.grades, "state": x.states, "citizenship": x.citizens_only,
               "cost": x.cost, "deadline": x.deadline}
        for f in FIELDS:
            stated, answered = f not in l.omitted, f not in x.unknown
            if stated and answered:
                out[f]["correct" if truth[f] == got[f] else "wrong"] += 1
            elif stated:
                out[f]["missed"] += 1              # text had it, extractor said unknown
            elif answered:
                out[f]["invented"] += 1            # text did not have it, extractor gave a value
            else:
                out[f]["unknown_ok"] += 1
    res = {}
    for f, c in out.items():
        stated = c["correct"] + c["wrong"] + c["missed"]
        absent = c["invented"] + c["unknown_ok"]
        res[f] = {"stated": stated, "correct": c["correct"], "wrong": c["wrong"], "missed": c["missed"],
                  "accuracy_pct": round(100 * c["correct"] / stated, 2) if stated else None,
                  "not_stated": absent, "invented": c["invented"]}
    return res


def all_fields_right(listings, xs):
    n = 0
    for l, x in zip(listings, xs):
        o = l.truth
        ok = tuple(sorted(o.states)) == x.states and o.citizens_only == x.citizens_only
        ok = ok and set(x.unknown) == set(l.omitted)
        ok = ok and ("grade" in l.omitted or o.grades == x.grades)
        ok = ok and ("cost" in l.omitted or o.cost == x.cost)
        ok = ok and ("deadline" in l.omitted or o.deadline == x.deadline)
        n += ok
    return round(100 * n / len(listings), 2)


def ranking(listings, studs, xs):
    truth = [l.truth for l in listings]
    extracted = [Opportunity(o.id, o.title, o.text, o.kind, x.grades, x.states, x.citizens_only, x.cost,
                             x.deadline, (), x.unknown) for o, x in zip(truth, xs)]
    naive = [naive_opportunity(o, l.posted) for o, l in zip(truth, listings)]
    i_truth, i_ext, i_naive = Index(truth), Index(extracted), Index(naive)
    methods = {
        "no rules": lambda s: i_truth.search(s, TODAY, K, filter="none"),
        "naive regex rules": lambda s: i_naive.search(s, TODAY, K),
        "extract.py, hide unknown": lambda s: i_ext.search(s, TODAY, K, unknown="hide"),
        "extract.py, show unknown": lambda s: i_ext.search(s, TODAY, K, unknown="show"),
        "hand-labelled rules (ceiling)": lambda s: i_truth.search(s, TODAY, K),
    }
    rows = {}
    for name, fn in methods.items():
        useful = shown = inelig = flagged = flagged_bad = unflagged_bad = 0
        for s, tp in studs:
            for r in fn(s):
                o = truth[r.opp.id]
                ok = not check(o, s, TODAY)
                shown += 1
                useful += ok and bool(tp & set(o.topics))
                inelig += not ok
                flagged += bool(r.verify)
                flagged_bad += bool(r.verify) and not ok
                unflagged_bad += (not r.verify) and not ok
        n = len(studs)
        rows[name] = {"useful_per_10": round(useful / n, 2), "shown": round(shown / n, 2),
                      "ineligible_per_10": round(inelig / n, 2),
                      "ineligible_unflagged_per_10": round(unflagged_bad / n, 3),
                      "flagged_verify_per_10": round(flagged / n, 2)}
    # Whole catalog, not just the top 10: how many truly eligible listings do the extracted rules hide?
    elig = hidden_show = hidden_hide = 0
    for s, _ in studs:
        t = i_truth.eligible(s, TODAY)
        elig += len(t)
        hidden_show += len(t - i_ext.eligible(s, TODAY, "show"))
        hidden_hide += len(t - i_ext.eligible(s, TODAY, "hide"))
    lat = []
    for s, _ in studs:
        t0 = time.perf_counter()
        i_ext.search(s, TODAY, K)
        lat.append((time.perf_counter() - t0) * 1000)
    lat.sort()
    return {"methods": rows,
            "eligible_mean": round(elig / len(studs), 1),
            "eligible_hidden_pct_show": round(100 * hidden_show / elig, 2),
            "eligible_hidden_pct_hide": round(100 * hidden_hide / elig, 2),
            "listings_with_unknown_field_pct": round(100 * sum(bool(o.unknown) for o in extracted) / len(extracted), 1),
            "search_ms_median": round(statistics.median(lat), 2),
            "search_ms_p95": round(lat[int(0.95 * len(lat))], 2)}


def run(name, listings, studs, extractor=extract):
    """extractor: any function (text, as_of, today) -> extract.Extracted. The regex extractor is the
    default; a different one (for example a language model behind the same return type) can be
    scored on the same listings by passing it here."""
    t0 = time.perf_counter()
    xs = [extractor(l.truth.text, l.posted, TODAY) for l in listings]
    per = (time.perf_counter() - t0) * 1000 / len(listings)
    out = {"listings": len(listings), "students": len(studs), "fields": field_scores(listings, xs),
           "all_fields_right_pct": all_fields_right(listings, xs), "extract_ms_per_listing": round(per, 3)}
    out.update(ranking(listings, studs, xs))
    print("== %s: %d listings, %d students" % (name, out["listings"], out["students"]))
    print("%-12s %7s %8s %6s %7s %9s %11s %9s" % ("field", "stated", "correct", "wrong", "missed", "accuracy", "not stated", "invented"))
    for f, r in out["fields"].items():
        print("%-12s %7d %8d %6d %7d %8.2f%% %11d %9d" % (f, r["stated"], r["correct"], r["wrong"], r["missed"],
                                                         r["accuracy_pct"], r["not_stated"], r["invented"]))
    print("listings with every field right: %.2f%%" % out["all_fields_right_pct"])
    print()
    print("%-30s %7s %6s %11s %12s %8s" % ("rules used for the top 10", "useful", "shown", "ineligible", "inel. unflag", "flagged"))
    for m, r in out["methods"].items():
        print("%-30s %7.2f %6.2f %11.2f %12.3f %8.2f" % (m, r["useful_per_10"], r["shown"], r["ineligible_per_10"],
                                                       r["ineligible_unflagged_per_10"], r["flagged_verify_per_10"]))
    print("truly eligible listings hidden by extracted rules: %.2f%% (show unknown), %.2f%% (hide unknown)"
          % (out["eligible_hidden_pct_show"], out["eligible_hidden_pct_hide"]))
    print("listings with at least one unknown field: %.1f%%" % out["listings_with_unknown_field_pct"])
    print("extract %.3f ms per listing, search median %.2f ms, p95 %.2f ms" %
          (out["extract_ms_per_listing"], out["search_ms_median"], out["search_ms_p95"]))
    print()
    return out


def main(n=3000, n_students=300):
    out = {"today": TODAY.isoformat(), "k": K, "data": "synthetic"}
    here = os.path.dirname(os.path.abspath(__file__))
    try:
        with open(os.path.join(here, "round1_results.json")) as f:
            r1 = json.load(f)
        print("== recorded: version 1 of extract.py on set A, before the fixes (round1_results.json)")
        print("listings with every field right: %.2f%%, useful per 10 (hide unknown): %.2f\n" % (
            r1["all_fields_right_pct"], r1["methods"]["extract.py, hide unknown"]["useful_per_10"]))
    except (OSError, ValueError, KeyError):
        pass
    out["tuning"] = run("tuning (gen.py wordings, seed 1)", text_catalog(n, TODAY, seed=1), students(n_students, seed=2))
    out["set_a_dev"] = run("set A (second wordings, now a development set)", heldout_catalog(n, TODAY), students(n_students, seed=202))
    out["set_b_heldout"] = run("set B (third wordings, held out)", fresh_catalog(n, TODAY), students(n_students, seed=404))
    with open(os.path.join(here, "bench_results.json"), "w") as f:
        json.dump(out, f, indent=1)
    return out


if __name__ == "__main__":
    main(*(int(a) for a in sys.argv[1:3]))
