"""extract: turn the free-text eligibility paragraph of a listing into the rule fields shortlist uses.

    extract(text, as_of) -> Extracted(grades, states, citizens_only, cost, deadline, unknown, evidence)

Each field is one of three things: stated (a value), stated as open (no restriction), or not
stated. For grade, cost and deadline "not stated" is reported in `unknown` instead of being
guessed, because a guessed deadline hides a listing or shows a dead one without anyone noticing.
State and citizenship default to "no restriction" when the text is silent.

`as_of` is the date the listing was collected. It is needed to resolve dates written without a
year ("due March 1"). `today` is the date of the query, needed for graduation years ("Class of
2028" is grade 11 in one school year and grade 12 in the next).

Regular expressions only. Standard library only.
"""
import datetime as dt
import re
from dataclasses import dataclass, field

OPEN_DEADLINE = "2099-01-01"
ALL_GRADES = (9, 10, 11, 12)

MONTHS = {m: i + 1 for i, m in enumerate(
    "jan feb mar apr may jun jul aug sep oct nov dec".split())}
_MON = (r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|"
        r"Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)")

STATES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA",
    "colorado": "CO", "connecticut": "CT", "delaware": "DE", "florida": "FL", "georgia": "GA",
    "hawaii": "HI", "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD", "massachusetts": "MA",
    "michigan": "MI", "minnesota": "MN", "mississippi": "MS", "missouri": "MO", "montana": "MT",
    "nebraska": "NE", "nevada": "NV", "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM",
    "new york": "NY", "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT", "vermont": "VT",
    "west virginia": "WV", "virginia": "VA", "washington": "WA", "wisconsin": "WI", "wyoming": "WY",
    "district of columbia": "DC",
}
_ABBR = set(STATES.values())
_STATE_NAME = re.compile(r"\b(" + "|".join(sorted(STATES, key=len, reverse=True)) + r")\b", re.I)


@dataclass
class Extracted:
    grades: tuple = ALL_GRADES
    states: tuple = ()
    citizens_only: bool = False
    cost: int = 0
    deadline: str = OPEN_DEADLINE
    unknown: tuple = ()                 # subset of ("grade", "cost", "deadline")
    evidence: dict = field(default_factory=dict)   # field -> the sentence the value came from
    notes: list = field(default_factory=list)


def normalise(text):
    t = text.replace("\u2013", "-").replace("\u2014", "-").replace("\u2019", "'")
    t = re.sub(r"\bU\.\s?S\.(?:A\.)?", "US", t)
    t = re.sub(r"\b(Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sept|Sep|Oct|Nov|Dec)\.", r"\1", t)
    t = re.sub(r"\bMay\.(?=\s*\d)", "May", t)
    return t


def sentences(text):
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9$\"(])|\n+", normalise(text))
    return [p.strip() for p in parts if p.strip()]


def _nearest(cues, sent, start, end):
    """Label of the cue closest to sent[start:end]. A cue after the span costs 12 extra characters,
    so "tuition is $3,000 and aid up to $1,000" reads the first amount as tuition."""
    best = None
    for rx, label in cues:
        for m in rx.finditer(sent):
            if m.end() <= start:
                d = start - m.end()
            elif m.start() >= end:
                d = m.start() - end + 12
            else:
                d = 0
            if best is None or d < best[0]:
                best = (d, label)
    return best[1] if best else None


# ---------------------------------------------------------------- grade

_NAME = {"freshman": 9, "freshmen": 9, "sophomore": 10, "sophomores": 10, "junior": 11,
         "juniors": 11, "senior": 12, "seniors": 12, "ninth": 9, "tenth": 10, "eleventh": 11,
         "twelfth": 12}
_GRADE_WORD = re.compile(r"\b(freshm[ae]n|sophomores?|juniors?|seniors?|ninth|tenth|eleventh|twelfth)\b", re.I)
_NOT_A_GRADE = re.compile(r"\s+(?:researchers?|scientists?|faculty|engineers?|staff|fellows?|mentors?|"
                          r"counselors?|leaders?|lecturers?|partners?|advisors?|year)\b", re.I)
_COLLEGE = re.compile(r"\b(?:college|undergraduate|university)\b[^.;:]{0,25}$", re.I)
# Sentences about who came before, not about who may apply. Used for grade-free fields too.
_HISTORY = re.compile(r"\b(?:last year|past (?:years?|cohorts?|participants?|winners?)|previous(?:ly)?|"
                      r"alumni|have (?:earned|won|gone on)|included|has hosted|since (?:19|20)\d\d)\b", re.I)
_SINGULAR_OK = re.compile(r"(?:\ba|\ban|current|rising|incoming|or|and|least a|least an)\s+$", re.I)
_JOIN = r"(?:\s*(?:,|-|to|through|thru|and|or|&)\s*)"
_NUM_A = re.compile(r"\bgrades?\s+((?:\d{1,2}(?:th)?" + _JOIN + r"?)+)", re.I)
_NUM_B = re.compile(r"((?:\b\d{1,2}(?:th)?" + _JOIN + r"?)+)\s*-?\s*grade(?:rs?|s)?\b", re.I)
_RANGE_GAP = re.compile(r"\s*(?:grade|graders?)?\s*(?:-|to|through|thru)\s*(?:grade)?\s*", re.I)
_UP = re.compile(r"\s*(?:grade|graders?)?\s*(?:or|and)\s+(?:above|up|older|higher|beyond|later)\b", re.I)
_DOWN = re.compile(r"\s*(?:grade|graders?)?\s*(?:or|and)\s+(?:below|under|younger|lower|earlier)\b", re.I)
_AT_LEAST = re.compile(r"at least (?:a |an |in )?$", re.I)
_RISING = re.compile(r"\b(?:rising|entering|incoming|will be|about to (?:enter|start))\b", re.I)
_NEG_SENT = re.compile(r"\b(?:not eligible|ineligible|may not apply|cannot apply|can't apply|"
                       r"not open to|are excluded|is excluded)\b", re.I)
_NEG_TAIL = re.compile(r",?\s*\b(?:except|excluding|but not|other than)\b", re.I)
_ALL_HS = re.compile(r"\b(?:high school (?:students?|applicants?)|high schoolers|"
                     r"students? (?:currently )?(?:enrolled )?in high school)\b", re.I)
_CLASS_OF = re.compile(r"\bclass(?:es)? of ((?:(?:20\d\d)(?:\s*(?:,|and|or|-|through|to)\s*)?)+)", re.I)


def _grade_mentions(s):
    """[(start, end, grade)] for every grade named in one sentence, before any shifting."""
    found = {}
    for m in _GRADE_WORD.finditer(s):
        w = m.group(1).lower()
        if _NOT_A_GRADE.match(s, m.end()) or _COLLEGE.search(s[:m.start()]):
            continue
        if w in ("freshman", "sophomore", "junior", "senior") and not _SINGULAR_OK.search(s[:m.start()]):
            continue
        found[m.start()] = (m.start(), m.end(), _NAME[w])
    for rx in (_NUM_A, _NUM_B):
        for m in rx.finditer(s):
            for n in re.finditer(r"\d{1,2}", m.group(1)):
                g = int(n.group())
                if 1 <= g <= 12:
                    a = m.start(1) + n.start()
                    e = a + len(n.group())
                    if s[e:e + 2].lower() == "th":
                        e += 2
                    found[a] = (a, e, g)
    return [found[k] for k in sorted(found)]


def _grades_in(s):
    """Set of current grades one sentence names, with ranges, open ends and 'rising' applied."""
    ms = _grade_mentions(s)
    out = set()
    rising = _RISING.search(s)
    for i, (a, e, g) in enumerate(ms):
        gs = {g}
        if i + 1 < len(ms) and _RANGE_GAP.fullmatch(s[e:ms[i + 1][0]]):
            gs = set(range(min(g, ms[i + 1][2]), max(g, ms[i + 1][2]) + 1))
        if _UP.match(s, e) or _AT_LEAST.search(s[:a]):
            gs = set(range(g, 13))
        elif _DOWN.match(s, e):
            gs = set(range(9, g + 1))
        if rising and rising.start() < a:
            gs = {x - 1 for x in gs}      # a rising junior is in grade 10 today
        out |= gs
    return out


def _grade(sents, today):
    pos, neg, ev, all_hs = set(), set(), [], None
    end_year = today.year + (1 if today.month >= 7 else 0)   # year the current school year ends
    for s in sents:
        head, tail = s, ""
        cut = _NEG_TAIL.search(s)
        if cut:
            head, tail = s[:cut.start()], s[cut.end():]
        elif _NEG_SENT.search(s):
            head, tail = "", s
        p, n = _grades_in(head), _grades_in(tail)
        for m in _CLASS_OF.finditer(head):
            p |= {12 - (int(y) - end_year) for y in re.findall(r"20\d\d", m.group(1))}
        if p or n:
            ev.append(s)
        pos |= p
        neg |= n
        if all_hs is None and _ALL_HS.search(head):
            all_hs = s
    pos &= set(ALL_GRADES)
    if not pos and (all_hs or neg):
        pos = set(ALL_GRADES)
        if all_hs and all_hs not in ev:
            ev.append(all_hs)
    pos -= neg
    return (tuple(sorted(pos)) if pos else None), " ".join(ev)


# ---------------------------------------------------------------- state and citizenship

_RESIDE = re.compile(r"\b(?:residents?|residency|residing|reside|live in|living in|"
                     r"schools? in|students? (?:in|from)|applicants? (?:in|from)|"
                     r"enrolled in|based in)\b", re.I)
_NATION = re.compile(r"\b(?:nationwide|all 50 states|any (?:US )?state|every state|no residency|"
                     r"across the (?:country|US|United States)|anywhere in the (?:country|US|United States)|"
                     r"regardless of (?:state|location|where))\b", re.I)


def _state(sents):
    for s in sents:
        if _NATION.search(s):
            return (), s
    for s in sents:
        if not _RESIDE.search(s) or _HISTORY.search(s):
            continue
        got = {STATES[m.group(1).lower()] for m in _STATE_NAME.finditer(s)}
        got |= {w for w in re.findall(r"\b[A-Z]{2}\b", s) if w in _ABBR}
        if got:
            return tuple(sorted(got)), s
    return (), ""


_CITIZEN = re.compile(r"\b(?:(?:US|United States|American) (?:citizens?|citizenship|nationals?)|"
                      r"citizens? of the (?:US|United States)|permanent residents?|green card|"
                      r"citizenship)\b", re.I)
_CIT_OPEN = re.compile(r"\b(?:not required|not a requirement|no citizenship|regardless of (?:citizenship|"
                       r"immigration|status|nationality)|do(?:es)? not (?:need|have) to|need not|"
                       r"not (?:limited|restricted) to|any (?:citizenship|nationality|country)|"
                       r"international (?:students?|applicants?)|all nationalities|non-citizens?|"
                       r"undocumented|DACA)\b", re.I)


def _citizen(sents):
    for s in sents:
        if _CITIZEN.search(s):
            return (not _CIT_OPEN.search(s)), s
    return False, ""


# ---------------------------------------------------------------- cost

_MONEY = re.compile(r"(?:\$\s?(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?\s?([kK]\b)?(?!\s?(?:million|billion|[mMbB]\b))"
                    r"|\b(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?()\s?(?:dollars|USD)\b)")
_CLAUSE = re.compile(r"[,;]|\band\b|\bbut\b")
_APP_WORD = re.compile(r"\bappl|\bentry\b|\bregistration", re.I)
_COST_CUES = [
    (re.compile(r"\bapplication fees?|\bfees? to apply|\bentry fees?|\bregistration fees?|"
                r"\bprocessing fees?", re.I), "app"),
    (re.compile(r"\btuition|\bfees?\b|\bcosts?\b|\bprice|\bcharge|\bdeposit|\bpay\b|\bpays\b", re.I), "program"),
    (re.compile(r"\bstipends?|\bpaid\b|\bsalary|\bwages?|\bper hour|\bhourly|\bearn|"
                r"\bhonorarium", re.I), "paid"),
    (re.compile(r"\bprizes?|\bawards?\b|\bscholarships?|\bfinancial aid|\baid\b|\bwaivers?|\bgrants?\b|\bup to\b|\bworth\b|"
                r"\bvalued at|\bassistance", re.I), "aid"),
]
_FREE = re.compile(r"\b(?:free of charge|at no (?:cost|charge)|no (?:cost|charge)|tuition[- ]free|"
                   r"fully[- ]funded|costs? nothing|(?:all|every) (?:expenses?|costs?) (?:\w+ ){0,2}(?:covered|paid)|"
                   r"covers? all (?:expenses|costs)|no (?:\w+ )?fees?\b|without charge|"
                   r"(?:is|are) (?:completely |entirely |totally )?free|free to (?:attend|join|enter|participate|apply)|"
                   r"free (?:program|for (?:all|admitted|accepted|selected)))", re.I)
_FREE_THING = re.compile(r"\b(?:lunch|meals?|breakfast|dinner|snacks?|housing|parking|shirts?|"
                         r"transportation|wifi|admission to|materials)\b[^.;,]{0,25}$", re.I)


def _cost(sents):
    kinds, ev, paid = {}, [], False
    for s in sents:
        if _HISTORY.search(s):
            continue
        for m in _MONEY.finditer(s):
            g = m.groups()
            g = g[:3] if g[0] is not None else g[3:]
            amt = float(g[0].replace(",", "") + (g[1] or ""))
            if g[2]:
                amt *= 1000
            # Read the amount inside its own clause first, so "a $25 fee is due with the
            # application, and enrolled students pay $900" gives two different kinds of cost.
            cuts = [0] + [c.end() for c in _CLAUSE.finditer(s)] + [len(s)]
            a = max(c for c in cuts if c <= m.start())
            b = min((c for c in cuts if c >= m.end()), default=len(s))
            clause = s[a:b]
            label = _nearest(_COST_CUES, clause, m.start() - a, m.end() - a)
            if label is None:
                label = _nearest(_COST_CUES, s, m.start(), m.end())
            if label == "program" and _APP_WORD.search(clause):
                label = "app"
            if label in ("app", "program"):
                kinds[label] = min(kinds.get(label, amt), amt)   # two prices: take the cheaper option
                ev.append(s)
            elif label == "paid":
                paid = True
                ev.append(s)
        for m in _FREE.finditer(s):
            if _FREE_THING.search(s[:m.start()]):
                continue                                         # "lunch is free" is not the price
            around = s[max(0, m.start() - 25):m.end() + 12].lower()
            k = "app" if "appl" in around or "entry" in around else "program"
            kinds.setdefault(k, 0)
            ev.append(s)
    ev = " ".join(dict.fromkeys(ev))
    if kinds:
        return int(round(sum(kinds.values()))), ev
    if paid:
        return 0, ev
    return None, ""


# ---------------------------------------------------------------- deadline

_D1 = re.compile(r"\b(" + _MON + r")\s+(\d{1,2})(?:st|nd|rd|th)?(?!\d)(?:,?\s+(\d{4}))?\b")
_D2 = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?(" + _MON + r")\b(?:,?\s+(\d{4}))?")
_D3 = re.compile(r"(?<![\d/])(\d{1,2})/(\d{1,2})/(\d{4}|\d{2})(?![\d/])")
_D4 = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_DATE_CUES = [
    (re.compile(r"\bdeadlines?|\bdue\b|\bapply by|\bsubmit\w* by|\breceived by|\bno later than|"
                r"\bcloses?\b|\bclosing|\bpostmarked|\baccepted\b|\blast day|\bin by\b|\bcutoff", re.I), "deadline"),
    (re.compile(r"\bopens?\b|\bopening|\bbegins?|\bstarts?|\bruns?\b|\bheld\b|\btakes place|\bsessions?|"
                r"\bdecisions?|\bnotif\w+|\bannounc\w+|\binterviews?|\borientation|\bends?\b|\bfounded|"
                r"\bresults|\bfinalists|\bkickoff|\bmeets?\b", re.I), "other"),
]
_ROLLING = re.compile(r"\b(?:rolling|no (?:application )?deadline|year[- ]round|at any time|ongoing basis)\b", re.I)


def _mk(y, mo, d):
    try:
        return dt.date(y, mo, d)
    except ValueError:
        return None


def _dates(s, as_of):
    """[(start, end, date, year_was_inferred)] for every date written in one sentence."""
    out = []

    def add(m, mo, d, y):
        if any(a < m.end() and m.start() < b for a, b, _, _ in out):
            return
        if y is None:
            day = _mk(as_of.year, mo, d)
            if day is not None and day < as_of:
                day = _mk(as_of.year + 1, mo, d)
            inferred = True
        else:
            day = _mk(y + 2000 if y < 100 else y, mo, d)
            inferred = False
        if day:
            out.append((m.start(), m.end(), day, inferred))

    for m in _D4.finditer(s):
        add(m, int(m.group(2)), int(m.group(3)), int(m.group(1)))
    for m in _D1.finditer(s):
        add(m, MONTHS[m.group(1)[:3].lower()], int(m.group(2)), int(m.group(3)) if m.group(3) else None)
    for m in _D2.finditer(s):
        add(m, MONTHS[m.group(2)[:3].lower()], int(m.group(1)), int(m.group(3)) if m.group(3) else None)
    for m in _D3.finditer(s):
        if 1 <= int(m.group(1)) <= 12:
            add(m, int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return out


def _deadline(sents, as_of, notes):
    best, rolling = None, None
    for s in sents:
        for a, e, day, inferred in _dates(s, as_of):
            if _nearest(_DATE_CUES, s, a, e) == "deadline" and (best is None or day > best[0]):
                best = (day, s, inferred)       # priority and final deadline: keep the later one
        if rolling is None and _ROLLING.search(s):
            rolling = s
    if best:
        if best[2]:
            notes.append("deadline year inferred from collection date")
        return best[0].isoformat(), best[1]
    if rolling:
        return OPEN_DEADLINE, rolling
    return None, ""


# ---------------------------------------------------------------- public

def extract(text, as_of, today=None):
    """as_of: date the listing was collected. today: date of the query (defaults to as_of); a
    graduation year only maps to a grade relative to the current school year."""
    sents = sentences(text)
    x = Extracted()
    unknown = []
    g, x.evidence["grade"] = _grade(sents, today or as_of)
    if g is None:
        unknown.append("grade")
    else:
        x.grades = g
    x.states, x.evidence["state"] = _state(sents)
    x.citizens_only, x.evidence["citizenship"] = _citizen(sents)
    c, x.evidence["cost"] = _cost(sents)
    if c is None:
        unknown.append("cost")
    else:
        x.cost = c
    d, x.evidence["deadline"] = _deadline(sents, as_of, x.notes)
    if d is None:
        unknown.append("deadline")
    else:
        x.deadline = d
    x.unknown = tuple(unknown)
    x.evidence = {k: v for k, v in x.evidence.items() if v}
    return x


def to_opportunity(id, title, text, as_of, kind="program", today=None):
    """Build a shortlist.Opportunity from raw listing text. Fields the text does not state are left
    at their permissive defaults and named in `unknown`, so search can flag them."""
    from shortlist import Opportunity
    x = extract(text, as_of, today)
    return Opportunity(id, title, text, kind, x.grades, x.states, x.citizens_only, x.cost,
                       x.deadline, (), x.unknown)
