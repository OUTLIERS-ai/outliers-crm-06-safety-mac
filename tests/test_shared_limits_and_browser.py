"""Test: the limit is shared, and only one thing drives the browser.

What should be true (Layer 6):

- One counter for everything. Three activities each staying inside their own
  private allowance is exactly how a total nobody agreed to gets reached, and
  every part looks well behaved in its own log while it happens.
- One driver at a time. Two automated jobs in the same browser profile fight over
  the same session, and the damage shows up days later as an account that no
  longer trusts the login.

Run:  python tests/test_shared_limits_and_browser.py
"""

import json
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))

import browser_lock
import crm_paths
import limits

FAILS = []


def check(label, cond, detail=""):
    ok = bool(cond)
    print(("  PASS  " if ok else "  FAIL  ") + label
          + (("   [" + detail + "]") if detail and not ok else ""))
    if not ok:
        FAILS.append(label)


VAULT = Path(tempfile.mkdtemp(prefix="crm-layer6-limits-"))
crm_paths.use_vault(VAULT)
(VAULT / "_layers").mkdir(parents=True)
(VAULT / "_layers" / "config.json").write_text(
    json.dumps({"daily-cap": 6, "layer": 5}), encoding="utf-8")
limits.reset()

print("\n=== 1. the cap comes from your config, not from the code ===")

check("the cap is read from the config file", limits.cap_from_config() == 6,
      str(limits.cap_from_config()))
check("nothing has been counted yet", limits.total() == 0)
check("everything is still allowed", limits.allow("message")[0] is True)

print("\n=== 2. three well-behaved activities share one budget ===")

for kind in ("message", "connection", "comment"):
    for _ in range(2):
        limits.record(kind)

check("each activity did only two things",
      limits.counts() == {"message": 2, "connection": 2, "comment": 2},
      str(limits.counts()))
check("the shared total is six", limits.total() == 6)

allowed, reason = limits.allow("message")
check("a seventh thing is refused even though no single activity did much",
      allowed is False, reason)
check("the refusal explains the shared total", "6" in reason, reason)
check("and it breaks down what used it up",
      "message" in reason and "connection" in reason, reason)

allowed_other, _ = limits.allow("comment")
check("a different activity is refused for the same reason", allowed_other is False,
      "counting activities separately is how the total gets away from you")

print("\n=== 3. the count is of what happened, not what was planned ===")

limits.reset()
check("resetting clears it", limits.total() == 0)
before = limits.total()
limits.allow("message")
check("asking permission does not spend budget", limits.total() == before)
limits.record("message")
check("doing the thing does", limits.total() == before + 1)

print("\n=== 4. the count starts again when the date changes ===")

stale = {"day": "2000-01-01", "counts": {"message": 99}}
(VAULT / "_state").mkdir(parents=True, exist_ok=True)
(VAULT / "_state" / "activity.json").write_text(json.dumps(stale), encoding="utf-8")
check("yesterday's count does not spend today's budget", limits.total() == 0,
      str(limits.counts()))

print("\n=== 5. one thing drives the browser ===")

limits.reset()
token = browser_lock.acquire("collector")
check("the first job gets the lock", bool(token))
check("the lock says who holds it",
      browser_lock.current()["owner"] == "collector",
      str(browser_lock.current()))

blocked = False
try:
    browser_lock.acquire("a second job")
except browser_lock.Busy as err:
    blocked = True
    message = str(err)
check("a second job is refused rather than joining in", blocked)
check("and is told who has it", blocked and "collector" in message, message if blocked else "")

check("a job cannot release a lock it does not hold",
      browser_lock.release("not-the-right-token") is False)
check("the holder can release it", browser_lock.release(token) is True)
check("and then the lock is free", browser_lock.current() is None)

print("\n=== 6. the context manager releases even when the work fails ===")

raised = False
try:
    with browser_lock.held("collector"):
        raise RuntimeError("the page did not load")
except RuntimeError:
    raised = True
check("the error still reaches the caller", raised)
check("but the lock was given back", browser_lock.current() is None,
      "a lock left behind by a crash is worse than no lock")

print("\n=== 7. a lock left by a crashed job is reclaimed, and says so ===")

browser_lock.acquire("a job that then crashed")
old = json.loads(browser_lock.lock_path().read_text(encoding="utf-8"))
old["taken"] = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat(timespec="seconds")
browser_lock.lock_path().write_text(json.dumps(old), encoding="utf-8")

reclaimed = browser_lock.acquire("a new job")
check("a lock older than any real run is reclaimed", bool(reclaimed))
check("and the new job holds it",
      browser_lock.current()["owner"] == "a new job", str(browser_lock.current()))
browser_lock.release(reclaimed)

fresh = browser_lock.acquire("a job that is still running")
still_blocked = False
try:
    browser_lock.acquire("someone impatient")
except browser_lock.Busy:
    still_blocked = True
check("a lock that is merely recent is NOT reclaimed", still_blocked,
      "reclaiming too eagerly is the same as having no lock")
browser_lock.release(fresh)

shutil.rmtree(VAULT, ignore_errors=True)

print("\n%s" % ("ALL PASS" if not FAILS else "FAILURES: " + ", ".join(FAILS)))
sys.exit(1 if FAILS else 0)
