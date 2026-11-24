"""Demo: read rules out of six made-up listings, then build one student's shortlist.

Runs in about a second. The listings are written by hand for this demo and are not real programs.
"""
import datetime as dt
from extract import extract, to_opportunity
from shortlist import Index, Student, check

TODAY = dt.date(2026, 11, 1)
COLLECTED = dt.date(2026, 9, 15)

LISTINGS = [
    ("Prairie Robotics Summer Lab",
     "Six weeks building an autonomous robot with a university lab team. Applicants must be rising "
     "juniors and seniors. Open to students who attend school in IL, WI or IN. Tuition is $1,450 and "
     "there is a $50 application fee. Need-based scholarships of up to $1,500 are available. "
     "Priority deadline Jan 15; final deadline Feb 14, 2027. The program runs from June 14 to July 25, 2027."),
    ("Autonomous Drone Challenge",
     "Teams design a drone and a controller for a robotics course. Open to all high school students. "
     "There is no cost to participate. Top teams receive a $2,500 prize. Applications open "
     "September 1 and close October 10, 2026."),
    ("River City Robot Internship",
     "Paid internship programming robot sensors at a startup. Students in 11th grade or above may apply. "
     "Participants receive a $3,000 stipend. Applicants must be US citizens or permanent residents. "
     "Apply by 3/1/2027."),
    ("Mechatronics Scholars",
     "A robotics and mechatronics seminar led by senior researchers and junior faculty. "
     "Open to students in grades 9-10. The program fee is $400. Applications are due January 30, 2027."),
    ("Weekend Robot Builders",
     "Build and program a small robot over eight Saturdays. Lunch is free on program days. "
     "Open to high school students. Graduating seniors are not eligible. Held on campus in Chicago, IL."),
    ("National Robotics Fellowship",
     "A year of mentored robotics research with a robot arm. Eligibility: current juniors. "
     "The cost to attend is $6,000. The application deadline is December 5."),
]


def main():
    print("1. Rules read from the listing text (collected %s)\n" % COLLECTED)
    for title, text in LISTINGS:
        x = extract(text, COLLECTED, TODAY)
        print(title)
        print("   grades %s | states %s | citizens only %s | cost %s | deadline %s" % (
            "?" if "grade" in x.unknown else "-".join(map(str, (x.grades[0], x.grades[-1]))),
            ",".join(x.states) or "any", x.citizens_only,
            "?" if "cost" in x.unknown else "$%d" % x.cost,
            "?" if "deadline" in x.unknown else x.deadline))
        for f in ("cost", "deadline"):
            if f in x.evidence:
                print("   %-8s from: %s" % (f, x.evidence[f]))
        if x.unknown:
            print("   not stated: %s" % ", ".join(x.unknown))
    opps = [to_opportunity(i, t, text, COLLECTED, today=TODAY) for i, (t, text) in enumerate(LISTINGS)]
    idx = Index(opps)
    me = Student(grade=10, state="IL", interests="I want to build robots and drones", citizen=True, budget=2000)
    print("\n2. Shortlist on %s for a grade 10 student in IL with a $2,000 budget\n" % TODAY)
    for r in idx.search(me, TODAY):
        flag = "  CHECK: " + ", ".join(r.verify) if r.verify else ""
        due = "no date" if "deadline" in r.verify else "due in %d days" % r.days_left
        print("   %5.2f  %-28s %-15s%s" % (r.score, r.opp.title, due, flag))
    print("\n3. Left out, with the reason\n")
    for o in opps:
        why = check(o, me, TODAY)
        if why:
            print("   %-28s %s" % (o.title, ", ".join(why)))
    print("\n4. Same search with unknown='hide'\n")
    for r in idx.search(me, TODAY, unknown="hide"):
        print("   %5.2f  %s" % (r.score, r.opp.title))


if __name__ == "__main__":
    main()
