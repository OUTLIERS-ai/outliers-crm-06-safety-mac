"""Test: the gate refuses, and a passing verdict is still not a sent message.

What should be true (Layer 6): nothing reaches a person without your hand, and a
hold cannot be got round. Those are the two things this layer is for, and both
are tested here by watching the gate say no.

The important shape of these tests: there is no test called "it sends
successfully", because there is nothing that sends. The best outcome the gate can
produce is a file in your outbox marked unsent, with a note telling you to send
it yourself.

Run:  python tests/test_send_gate_refuses.py
"""

import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))

import crm_paths
import holds
import limits
import review
import sendgate

FAILS = []


def check(label, cond, detail=""):
    ok = bool(cond)
    print(("  PASS  " if ok else "  FAIL  ") + label
          + (("   [" + detail + "]") if detail and not ok else ""))
    if not ok:
        FAILS.append(label)


VAULT = Path(tempfile.mkdtemp(prefix="crm-layer6-gate-"))
crm_paths.use_vault(VAULT)
(VAULT / "_layers").mkdir(parents=True)
(VAULT / "_layers" / "config.json").write_text(
    json.dumps({"daily-cap": 5, "layer": 5}), encoding="utf-8")
(VAULT / "People").mkdir(parents=True)
(VAULT / "People" / "Rowan Ashdown.md").write_text(
    "---\nname: Rowan Ashdown\n"
    "linkedin-url: https://www.linkedin.com/in/rowanashdown\n---\n", encoding="utf-8")
limits.reset()


def message(**over):
    base = {
        "to": "Rowan Ashdown",
        "identifier": "https://www.linkedin.com/in/rowanashdown",
        "kind": "message",
        "body": "Saw you took on the studio next door. How is that going?",
        "author": "opener-writer",
        "item_id": "draft-1",
    }
    base.update(over)
    return base


def reasons_for(msg):
    return " ".join(sendgate.review_outbound(msg)["reasons"]).lower()


def failed_check(msg, cid):
    result = {c["id"]: c for c in sendgate.review_outbound(msg)["checks"]}
    return result[cid]["ok"] is False


print("\n=== 1. with nothing set up, it refuses ===")

verdict = sendgate.review_outbound(message())
check("a message nobody has reviewed is refused", verdict["refused"] is True)
check("the reason is that nobody but the writer has seen it",
      "approve" in " ".join(verdict["reasons"]).lower(), str(verdict["reasons"]))
check("the verdict itself says nothing was sent", verdict["sent"] is False)

print("\n=== 2. a properly reviewed message gets as far as your outbox ===")

review.submit("draft-1", author="opener-writer", summary="an opener")
review.approve("draft-1", reviewer="you")

verdict = sendgate.review_outbound(message())
check("now it passes every check", verdict["refused"] is False,
      str(verdict["reasons"]))
check("and it STILL reports itself as not sent", verdict["sent"] is False)
check("and says so in words", "no way to send" in verdict["note"].lower(),
      verdict["note"])

staged = sendgate.stage_for_you(message(), verdict)
text = Path(staged).read_text(encoding="utf-8")
check("it is written to your outbox", "outbox" in str(staged).lower(), str(staged))
check("the file says it has not been sent", "sent: false" in text)
check("it tells you that you have to send it",
      "send it yourself" in text.lower())
check("the message itself is there for you to copy",
      "How is that going?" in text)

print("\n=== 3. a hold beats everything above it ===")

holds.hold("Rowan Ashdown", reason="you picked that conversation up yourself")

verdict = sendgate.review_outbound(message())
check("the same, fully approved message is now refused", verdict["refused"] is True)
check("because the person is held", failed_check(message(), "not-held"))
check("the reason says so in plain words",
      "held" in reasons_for(message()), reasons_for(message()))

blocked = False
try:
    sendgate.stage_for_you(message())
except ValueError:
    blocked = True
check("and it cannot even be staged for you", blocked)

print("\n=== 4. the hold cannot be got round by changing the identifier ===")

check("not by using only the name",
      sendgate.review_outbound(message(identifier=""))["refused"] is True)
check("not by using only the link",
      sendgate.review_outbound(message(to=""))["refused"] is True)
check("not by putting tracking parameters on the link",
      sendgate.review_outbound(
          message(identifier="https://www.linkedin.com/in/rowanashdown/?trk=x")
      )["refused"] is True)
check("not by decorating the name",
      sendgate.review_outbound(message(to="* Rowan Ashdown"))["refused"] is True)

holds.release("Rowan Ashdown")
check("and once you release them, the gate lets it through again",
      sendgate.review_outbound(message())["refused"] is False,
      str(sendgate.review_outbound(message())["reasons"]))

print("\n=== 5. an unidentifiable recipient is refused, never assumed safe ===")

check("no name and no link is refused",
      failed_check(message(to="", identifier=""), "recipient-identified"))
check("because there is no way to check them against the hold list",
      "hold list" in reasons_for(message(to="", identifier="")))

print("\n=== 6. the shared limit refuses regardless of what else passed ===")

for _ in range(5):
    limits.record("comment")
verdict = sendgate.review_outbound(message())
check("the message is refused when the shared budget is gone",
      verdict["refused"] is True)
check("even though the budget was used by a different activity",
      failed_check(message(), "room-in-shared-limit"))
check("and the reason says what used it", "comment" in reasons_for(message()),
      reasons_for(message()))
limits.reset()

print("\n=== 7. the writer approving itself is not an approval ===")

review.submit("draft-2", author="opener-writer")
try:
    review.approve("draft-2", reviewer="opener-writer")
except review.SelfApproval:
    pass
check("a self-approved message is refused by the gate",
      failed_check(message(item_id="draft-2"), "independently-approved"))

print("\n=== 8. a check that breaks refuses, rather than waving it through ===")

real = sendgate.check_not_held
sendgate.CHECKS[1] = ("not-held", lambda m: (_ for _ in ()).throw(RuntimeError("boom")))
try:
    verdict = sendgate.review_outbound(message())
    check("a broken hold check refuses the message", verdict["refused"] is True)
    check("and says it refused BECAUSE it could not check",
          "rather than assumed safe" in " ".join(verdict["reasons"]),
          str(verdict["reasons"]))
finally:
    sendgate.CHECKS[1] = ("not-held", real)

print("\n=== 9. an empty message is not a message ===")

check("an empty body is refused", failed_check(message(body="   "), "has-something-to-say"))

shutil.rmtree(VAULT, ignore_errors=True)

print("\n%s" % ("ALL PASS" if not FAILS else "FAILURES: " + ", ".join(FAILS)))
sys.exit(1 if FAILS else 0)
