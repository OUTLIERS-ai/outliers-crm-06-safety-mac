"""
sequence.py - what runs first, and what happens when a step fails.

Without a declared order, two things go wrong and neither announces itself.

The first is duplicated work. A step that scores records and a step that ranks
them both end up reading the same source, because nobody wrote down that one
comes after the other, so each fetches its own copy.

The second is worse. A step fails, and the steps after it run anyway on whatever
was there before. The output looks normal. It is yesterday's output wearing
today's date, and nothing in it says so.

This module takes a written plan and runs it. It refuses a plan that does not
make sense, it runs steps in dependency order, and when a step fails it does not
run anything that depended on it. Independent steps still run, because stopping
the whole system because one unrelated thing broke is its own kind of failure.

    import sequence
    plan = [
        {"name": "collect",  "does": "read the sources"},
        {"name": "score",    "after": ["collect"], "does": "form a view"},
        {"name": "rank",     "after": ["score"],   "does": "order the list"},
    ]
    report = sequence.run(plan, runner)

`runner(step)` returns True, or (False, "why"). It is your code; this module
never guesses what a step does.

Needs: Python 3.8 or newer. Nothing else.
"""

import sys

RAN = "ran"
FAILED = "failed"
SKIPPED = "not run"


class BadPlan(Exception):
    """The plan itself is wrong. Raised before anything runs."""


def validate(plan):
    """Check the plan before running a single step. Returns the ordered names.

    Checking first is the point. Discovering halfway through that step four
    depends on a step that does not exist means steps one to three have already
    happened and cannot be taken back.
    """
    if not plan:
        raise BadPlan("the plan is empty")

    names = []
    for step in plan:
        name = str(step.get("name", "")).strip()
        if not name:
            raise BadPlan("a step has no name; every step needs one")
        if name in names:
            raise BadPlan("two steps are called %r; names have to be unique" % name)
        names.append(name)

    known = set(names)
    for step in plan:
        for dep in step.get("after", []) or []:
            if dep not in known:
                raise BadPlan("%r says it runs after %r, and there is no such step"
                              % (step["name"], dep))

    # Order by dependency, and refuse a loop. A loop is not a rare mistake: it is
    # what you get when two steps are each written to run "after the other one".
    ordered = []
    remaining = list(plan)
    while remaining:
        ready = [s for s in remaining
                 if all(d in ordered for d in (s.get("after") or []))]
        if not ready:
            stuck = ", ".join(sorted(str(s["name"]) for s in remaining))
            raise BadPlan("these steps depend on each other in a circle: %s" % stuck)
        for s in ready:
            ordered.append(s["name"])
            remaining.remove(s)
    return ordered


def run(plan, runner, stop_everything_on_failure=False):
    """Run the plan. Returns a report a person can read.

    Each result is one of: ran, failed, or not run. "not run" always carries the
    reason, because a step that silently did not happen is the failure mode this
    whole module exists to prevent.
    """
    order = validate(plan)
    by_name = {str(s["name"]): s for s in plan}

    results = {}
    details = {}
    for name in order:
        step = by_name[name]
        blocked = [d for d in (step.get("after") or []) if results.get(d) != RAN]
        if blocked:
            results[name] = SKIPPED
            details[name] = ("depends on %s, which did not run"
                             % ", ".join(sorted(blocked)))
            continue
        if stop_everything_on_failure and FAILED in results.values():
            results[name] = SKIPPED
            details[name] = "an earlier step failed and the plan stops on failure"
            continue
        try:
            outcome = runner(step)
        except Exception as err:
            results[name] = FAILED
            details[name] = "the step raised: %s" % err
            continue
        ok, why = (outcome if isinstance(outcome, tuple) else (outcome, ""))
        results[name] = RAN if ok else FAILED
        details[name] = str(why or ("done" if ok else "no reason given"))

    return {
        "order": order,
        "results": results,
        "details": details,
        "ran": [n for n in order if results[n] == RAN],
        "failed": [n for n in order if results[n] == FAILED],
        "not_run": [n for n in order if results[n] == SKIPPED],
        "ok": not any(v == FAILED for v in results.values()),
    }


def render(report):
    """The report as text. One line per step, in the order they were attempted."""
    out = ["step                      outcome   why", "-" * 66]
    for name in report["order"]:
        out.append("%-25s %-9s %s" % (name, report["results"][name],
                                      report["details"].get(name, "")))
    out.append("")
    out.append("%d ran, %d failed, %d not run."
               % (len(report["ran"]), len(report["failed"]), len(report["not_run"])))
    if report["failed"]:
        out.append("")
        out.append("Nothing downstream of a failed step was run. An output produced")
        out.append("from a failed step is yesterday's output with today's date on it.")
    return "\n".join(out)


def main(argv):
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
