# shortlist

Rank a catalog of opportunities for one student and only show the ones they can apply to, when the rules for each listing have to be read out of its text.

This is an independent prototype. All data in it is synthetic. It is not affiliated with, connected to, or reviewed by Deep24 or Ultra.

## The problem

A recommendation that matches a student's interests is not useful if the deadline has passed, it is only open to seniors, or it costs more than the family can pay. So a recommender for summer programs, competitions and scholarships needs hard rules as well as relevance.

The first version of this project assumed every listing already came with clean fields: a grade range, a list of states, a cost, a deadline. Real listings do not. They say "rising juniors and seniors", "tuition is $1,450 and there is a $50 application fee", "priority deadline Jan 15; final deadline Feb 14". The same paragraph also has dollar amounts that are not the price (stipends, prizes, scholarships), dates that are not the deadline (program dates, decision dates), and grade words that are not about applicants ("senior researchers"). Many listings leave the cost or deadline out entirely.

This version adds the missing step. `extract.py` reads the five rules from the text, and the ranker handles the case where a rule could not be read.

## Why I built it around Deep24

Deep24's Y Combinator page describes Ultra, a college admissions advisor whose recommendations are "drawing from a database of over 3,000 opportunities" for high school students, including internships with startups (https://www.ycombinator.com/companies/deep24). Their Software Engineering Intern posting asks interns to build production features, work on AI integrations, and take part in product experiments (https://www.ycombinator.com/companies/deep24/jobs/HQOPclv-software-engineering-intern).

I do not know how their database is built or what their pipeline looks like. My assumption is that a catalog of that size is collected from many sources with inconsistent wording, which is the problem this project is about. The benchmark here is written so that a different extractor, such as a language model, can be scored on the same listings.

## What it does

- `extract(text, as_of, today)` returns grades, states, citizenship requirement, cost and deadline, plus the sentence each value came from. Grade, cost and deadline can come back as unknown.
- `check(opportunity, student, today)` returns the reasons a student cannot apply. An unknown field never excludes a listing.
- `Index.search(student, today, k, unknown="show")` ranks eligible listings with BM25. Listings with unknown fields are either shown with a `verify` flag naming what to confirm, or hidden with `unknown="hide"`.
- `bench.py` scores the extractor field by field and scores the final top 10 against the rules the generator wrote the text from.

## Architecture

| file | role |
|---|---|
| `shortlist.py` | `Opportunity`, `Student`, `check`, and the BM25 `Index` |
| `extract.py` | free text to rule fields, regular expressions only |
| `gen.py` | synthetic catalog, students, and the tuning wordings |
| `heldout.py` | two more sets of wordings the extractor was not developed against |
| `bench.py` | field accuracy and top 10 quality on all three sets |
| `demo.py` | six hand-written listings, end to end |
| `test_shortlist.py`, `test_extract.py` | 56 tests |
| `bench_results.json`, `round1_results.json` | output of the runs reported below |

The generator writes each listing's rules first, then writes the text from them, so the correct answer for every field is known. The extractor only ever sees the text and the collection date.

## Key decisions and tradeoffs

**Unknown is an answer.** For grade, cost and deadline the extractor reports "not stated" instead of a default. A guessed deadline either hides a live listing or shows a dead one, and nobody can tell which. State and citizenship default to "no restriction" when the text is silent, because flagging every listing that does not mention citizenship would make the flag meaningless. That default is a real risk for listings that have an unstated restriction.

**Nearest cue decides what a number means.** Each dollar amount and date is labelled by the closest cue word, first inside its own clause and then in the sentence. That is how "Tuition is $1,450 and there is a $50 application fee" becomes $1,500, a stipend becomes a cost of 0, and "applications open September 1 and close October 10" gives October 10.

**"Rising" shifts the grade.** A rising junior is in grade 10 when they apply, so "rising juniors and seniors" is stored as grades 10 and 11.

**A graduation year needs the query date.** "Class of 2028" is grade 11 in one school year and grade 12 in the next. My first version resolved it against the date the listing was collected, which was wrong for any listing collected before July. The held-out run found this.

**A date with no year resolves to the next occurrence after the collection date,** and the result carries a note saying the year was inferred.

**Show or hide unknowns is a product choice, so I measured both.** Hiding gives a cleaner top 10 and throws away a large share of listings the student could have used. Showing keeps them and puts the checking on the student.

**Rules are checked while walking down the ranking,** not for the whole catalog on every query. The first version checked all 3,000 listings per search.

**Regular expressions, no model.** This had to run offline with no keys. The results below show where that choice runs out.

## Install and usage

Python 3.9 or newer. Nothing to install.

```
python3 demo.py                # about a second
python3 -m unittest            # 56 tests, about 2 seconds
python3 bench.py               # all three sets, 1 to 3 minutes
python3 bench.py 500 50        # smaller run: 500 listings, 50 students
```

```python
import datetime as dt
from extract import to_opportunity
from shortlist import Index, Student

today = dt.date(2026, 11, 1)
opps = [to_opportunity(0, "Robotics Lab", "Build a robot. Open to rising juniors. Tuition is $100. "
                       "Apply by 3/1/2027.", as_of=dt.date(2026, 9, 15), today=today)]
me = Student(grade=10, state="IL", interests="robots", budget=500)
for r in Index(opps).search(me, today):
    print(r.opp.title, r.score, r.days_left, r.verify)
```

## Example

Part of the output of `python3 demo.py`. The listings are made up for the demo.

```
Prairie Robotics Summer Lab
   grades 10-11 | states IL,IN,WI | citizens only False | cost $1500 | deadline 2027-02-14
   cost     from: Tuition is $1,450 and there is a $50 application fee.
   deadline from: Priority deadline Jan 15; final deadline Feb 14, 2027.
River City Robot Internship
   grades 11-12 | states any | citizens only True | cost $0 | deadline 2027-03-01
   cost     from: Participants receive a $3,000 stipend.
   deadline from: Apply by 3/1/2027.
Weekend Robot Builders
   grades 9-11 | states any | citizens only False | cost ? | deadline ?
   not stated: cost, deadline

2. Shortlist on 2026-11-01 for a grade 10 student in IL with a $2,000 budget

    2.36  Weekend Robot Builders       no date          CHECK: cost, deadline
    0.34  Prairie Robotics Summer Lab  due in 105 days

3. Left out, with the reason

   Autonomous Drone Challenge   deadline passed
   River City Robot Internship  grade
   National Robotics Fellowship grade, cost
```

"Weekend Robot Builders" says "Lunch is free on program days" and "Held on campus in Chicago, IL". Neither is read as the price or as a residency rule.

## Tests and verified results

`python3 -m unittest` runs 56 tests: the 17 from the first version, unchanged, and 39 new ones covering each field, the traps above, impossible dates, empty and junk input, a 5,000 sentence input, both unknown policies, invalid arguments, and a check that the benchmark can score a plugged-in extractor. `python3 -W error -m unittest` also passes.

Everything below is from `python3 bench.py` on synthetic data: 3,000 listings and 300 students per set, top 10 per student. A result is useful when the student is truly eligible and the listing shares one of the student's two interest topics.

I evaluated in three rounds, because the first held-out result was bad enough that I wanted to see whether fixing it would generalise.

| set | how extract.py relates to it | listings with every field right |
|---|---|---|
| tuning (`gen.py` wordings) | developed against it | 100.00% |
| set A, version 1 of extract.py | held out at the time | 54.20% |
| set A, current extract.py | I read the failures and fixed five causes | 100.00% |
| set B (third set of wordings) | held out, run once, extractor not changed afterwards | 24.00% |

Fixing everything that set A exposed did not carry over to set B. A fresh set of wordings broke the extractor again, and worse. I wrote set B with phrasings I thought were natural and suspected might fail, so it is a hard set, but that is also what new sources would be. The version 1 result on set A is recorded in `round1_results.json`; it cannot be regenerated from the current code because the extractor has changed.

Set B, field by field:

| field | stated in text | correct | wrong value | missed (said unknown) | invented |
|---|---|---|---|---|---|
| grade | 2,636 | 1,543 (58.54%) | 297 | 796 | 77 |
| state | 3,000 | 2,638 (87.93%) | 362 | 0 | 0 |
| citizenship | 3,000 | 2,559 (85.30%) | 441 | 0 | 0 |
| cost | 2,675 | 1,885 (70.47%) | 0 | 790 | 0 |
| deadline | 2,696 | 1,772 (65.73%) | 0 | 924 | 0 |

The one part that held up is how it fails. For cost and deadline, all 1,714 failures on set B were "unknown" and none were a wrong value. State and citizenship cannot abstain, and that is where the wrong values are: all 441 citizenship errors are the sentence "Citizenship status does not affect eligibility", which it reads as a requirement, and 185 state errors are "Illinois and Ohio students only", which has none of the cue words it looks for. Other misses include "Students graduating in 2028", "Junior and senior year students", "There is no tuition", "Apply on or before March 1" and "Registration ends".

Top 10 quality on set B:

| rules used | useful (of 10) | ineligible shown | ineligible and not flagged |
|---|---|---|---|
| no rules | 1.77 | 8.22 | 8.22 |
| naive regex (first dollar amount, first date) | 3.07 | 6.74 | 6.74 |
| extract.py, hide unknown | 5.51 | 1.45 | 1.45 |
| extract.py, show unknown | 4.45 | 5.46 | 0.24 |
| hand-labelled rules (ceiling) | 9.46 | 0.00 | 0.00 |

For comparison, on the tuning set the same rows are 1.69, 3.15, 9.00, 7.62 and 9.36. So with wording it knows, extracted rules get within 0.36 of hand-labelled rules, and with wording it does not know they get a little over half way from the naive baseline to the ceiling.

The two policies trade off as expected. On set B, hiding unknowns hides 79.29% of the listings each student was truly eligible for, because 75.3% of listings had at least one unknown field. Showing unknowns hides 8.40% and puts 8.81 flagged results in each top 10.

On the tuning catalog, extraction took 0.721 ms per listing and a search took 3.33 ms at the median and 11.38 ms at the 95th percentile on the machine I ran it on.

## Limitations and next steps

- All data is synthetic and I wrote all three sets of wordings myself. Real listings will be more varied than any of them, so I would expect real accuracy to be closer to set B than to the tuning set, and possibly lower. I did not use or scrape any real opportunity database.
- The main result is that hand-written patterns do not generalise across wordings. The next step I would take is to put a language model behind the same `Extracted` return type, keep the unknown option, and score it with `bench.run(..., extractor=...)` on these sets and on a small hand-labelled sample of real listings. I did not do that here because I wanted the project to run with no API keys.
- State and citizenship need an unknown option too. Defaulting to "no restriction" is what turned set B's unfamiliar sentences into wrong values instead of flags.
- Only five rules are modelled. Income limits, school type, age, gender, prior coursework and GPA cutoffs are not.
- Text relevance is BM25 on words. A student who writes "coding" will not match a listing that only says "software". The synthetic topics make text ranking look easier than it is.
- Ranking is by relevance only. It does not weigh selectivity or how much a program would help an application.
- Deadlines are treated as fixed. A listing collected last year with no year on its date will resolve to a date that may no longer be right.
