"""Test: order is declared, failures stop what depended on them, and nothing
approves its own work.

What should be true (Layer 6):

- A plan that does not make sense is refused before any of it runs. Finding out
  halfway through that step four depends on a step that does not exist means
  steps one to three have already happened.
- When a step fails, nothing downstream of it runs. The alternative is an output
  built from a failed step, which looks exactly like a normal output and is
  yesterday's answer with today's date on it.
- Unrelated steps still run. Stopping everything because one thing broke is its
  own kind of failure.
- The author of a piece of work cannot approve it. Not because it would be
  dishonest, but because the reasoning that produced the mistake is the reasoning
  that would have to catch it, and to that reasoning the work looks right.

Run:  python tests/test_sequence_and_review.py
"""

import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))

import crm_paths
import review
import sequence

FAILS = []


def check(label, cond, detail=""):
    ok = bool(cond)
    print(("  PASS  " if ok else "  FAIL  ") + label
          + (("   [" + detail + "]") if detail and not ok else ""))
    if not ok:
        FAILS.append(label)


VAULT = Path(tempfile.mkdtemp(prefix="crm-layer6-sequence-"))
crm_paths.use_vault(VAULT)

PLAN = [
    {"name": "rank", "after": ["score"], "does": "order what is left"},
    {"name": "collect", "does": "read the sources"},
    {"name": "score", "after": ["collect"], "does": "form a view"},
    {"name": "tidy", "does": "unrelated housekeeping"},
]

print("\n=== 1. the order comes from the plan, not from the file ===")

order = sequence.validate(PLAN)
check("collecting happens before scoring",
      order.index("collect") < order.index("score"), str(order))
check("scoring happens before ranking",
      order.index("score") < order.index("rank"), str(order))
check("every step is in the order exactly once",
      sorted(order) == sorted(s["name"] for s in PLAN), str(order))

print("\n=== 2. a plan that cannot work is refused before anything runs ===")


def refuses(plan, because):
    try:
        sequence.validate(plan)
    except sequence.BadPlan as err:
        return because in str(err).lower()
    return False


check("a step depending on one that does not exist",
      refuses([{"name": "a", "after": ["nowhere"]}], "no such step"))
check("two steps with the same name",
      refuses([{"name": "a"}, {"name": "a"}], "unique"))
check("a step with no name at all",
      refuses([{"name": ""}], "no name"))
check("two steps each waiting for the other",
      refuses([{"name": "a", "after": ["b"]}, {"name": "b", "after": ["a"]}],
              "circle"))
check("an empty plan", refuses([], "empty"))

print("\n=== 3. every step runs, once, in order ===")

seen = []


def runner_all_fine(step):
    seen.append(step["name"])
    return True


report = sequence.run(PLAN, runner_all_fine)
check("nothing ran twice", len(seen) == len(set(seen)), str(seen))
check("everything ran", len(report["ran"]) == 4, str(report["results"]))
check("the report says the run was clean", report["ok"] is True)

print("\n=== 4. a failure stops what depended on it, and nothing else ===")

attempted = []


def runner_scoring_breaks(step):
    attempted.append(step["name"])
    if step["name"] == "score":
        return False, "the source returned nothing"
    return True


report = sequence.run(PLAN, runner_scoring_breaks)
check("the failing step is reported as failed", report["results"]["score"] == "failed")
check("the step that depended on it did not run",
      report["results"]["rank"] == "not run", str(report["results"]))
check("and it was never even attempted", "rank" not in attempted, str(attempted))
check("the reason names the step it was waiting for",
      "score" in report["details"]["rank"], report["details"]["rank"])
check("an unrelated step still ran", report["results"]["tidy"] == "ran")
check("the report does not claim success", report["ok"] is False)
check("the reason for the failure is carried through",
      "returned nothing" in report["details"]["score"], report["details"]["score"])

print("\n=== 5. a step that breaks outright is a failure, not a crash ===")


def runner_raises(step):
    if step["name"] == "collect":
        raise RuntimeError("the connection dropped")
    return True


report = sequence.run(PLAN, runner_raises)
check("a step that raises is recorded as failed",
      report["results"]["collect"] == "failed")
check("the error text is kept", "connection dropped" in report["details"]["collect"],
      report["details"]["collect"])
check("everything downstream is marked not run",
      report["results"]["score"] == "not run" and report["results"]["rank"] == "not run")
check("the rendered report says so in words",
      "not run" in sequence.render(report))

print("\n=== 6. the writer never approves its own work ===")

review.submit("draft-1", author="opener-writer", summary="a message to Rowan Ashdown")

self_approved = False
try:
    review.approve("draft-1", reviewer="opener-writer")
except review.SelfApproval:
    self_approved = True
check("the author is refused", self_approved)
check("and the item is still not approved", review.is_approved("draft-1") is False)

check("a different name approves it",
      review.approve("draft-1", reviewer="you")["approved"] is True)
check("and now it counts as approved", review.is_approved("draft-1") is True)

print("\n=== 7. the refusal cannot be got round by spelling it differently ===")

review.submit("draft-2", author="Opener Writer")
dodged = False
try:
    review.approve("draft-2", reviewer="  opener   writer  ")
except review.SelfApproval:
    dodged = True
check("different spacing and case is still the same author", dodged)
check("draft-2 remains unapproved", review.is_approved("draft-2") is False)

no_name = False
try:
    review.approve("draft-2", reviewer="")
except ValueError:
    no_name = True
check("an anonymous approval is not an approval", no_name)

check("work waiting for eyes is listed",
      "draft-2" in [r["id"] for r in review.waiting()],
      str([r["id"] for r in review.waiting()]))

shutil.rmtree(VAULT, ignore_errors=True)

print("\n%s" % ("ALL PASS" if not FAILS else "FAILURES: " + ", ".join(FAILS)))
sys.exit(1 if FAILS else 0)
