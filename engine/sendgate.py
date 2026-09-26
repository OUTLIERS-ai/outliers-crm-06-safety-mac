"""
sendgate.py - the last gate before a person. It can refuse, and it can hand you
something to look at. It cannot send.

Read that again, because it is the whole design. There is no function in this
file, or anywhere in this layer, that puts a message in front of another human
being. Not a disabled one, not one behind a flag, not one that needs a
confirmation first. There is no code for it. That absence is the guarantee, and
it is a stronger guarantee than any amount of care, because care is a property of
whoever is paying attention at the time.

What this file does is run every check the layer knows about and produce one of
two outcomes:

    refused          - with the reasons, in words
    ready for you    - written to your outbox for you to send by hand

The checks:

1. Is the recipient held? If you picked up that conversation yourself, nothing
   automatic goes near them.
2. Is there room inside the shared daily limit? Not this activity's limit. The
   shared one, counting everything.
3. Did somebody other than the author approve it? The writer never approves its
   own work.
4. Is there a recipient identifier at all? Somebody who cannot be identified
   cannot be checked against the hold list, and an unidentifiable recipient is
   therefore always refused rather than assumed to be fine.
5. Is there something to say? An empty message is a bug arriving as a message.

WHY "BE CAREFUL" IS NOT A CONTROL. An assistant instructed to be careful will
sometimes not be, and the failure shows up as a real message to a real person.
The restriction has to sit in the machinery, where it is a fact about what the
code can do, rather than in the instructions, where it is a hope about what it
will choose.

    import sendgate
    verdict = sendgate.review_outbound({
        "to": "Rowan Ashdown",
        "identifier": "https://www.linkedin.com/in/rowanashdown",
        "kind": "message",
        "body": "...",
        "author": "opener-writer",
        "item_id": "draft-1",
    })
    if verdict["refused"]:
        print(verdict["reasons"])       # and that is the end of it
    else:
        sendgate.stage_for_you(message)  # lands in your outbox, unsent

Needs: Python 3.8 or newer. Nothing else.
"""

import sys
from datetime import datetime, timezone

import crm_paths
import holds
import limits
import review
import safe_write

# Stated plainly so that anything importing this module can assert on it, and so
# that a reader looking for the send function knows it is not hiding elsewhere.
CAN_SEND = False


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ------------------------------------------------------------------- the checks
# Each returns (passed, reason). The reason is written to be read by a person in
# a log, so it says what happened rather than naming a rule.

def check_recipient_is_identified(message):
    ident = str(message.get("identifier") or "").strip()
    name = str(message.get("to") or "").strip()
    if not ident and not name:
        return False, ("no recipient is named, so this cannot be checked against "
                       "the hold list at all")
    if not ident:
        return True, ("only a name is known, which is enough to check but not "
                      "enough to be sure two people are not sharing it")
    return True, "recipient identified"


def check_not_held(message):
    ident = message.get("identifier")
    name = message.get("to")
    if holds.is_held_person(ident, name):
        return False, ("%s is held: you picked that conversation up yourself, and "
                       "nothing automatic goes near them until you say otherwise"
                       % (name or ident))
    return True, "not held"


def check_room_in_the_shared_limit(message):
    ok, reason = limits.allow(message.get("kind", "message"))
    return ok, reason


def check_independently_approved(message):
    item_id = message.get("item_id")
    author = message.get("author")
    if not item_id:
        return False, ("this was never submitted for review, so nobody has looked "
                       "at it but the thing that wrote it")
    record = review.record_for(item_id)
    if not record:
        return False, ("nothing was submitted for review under %r, so nobody has "
                       "approved this but the thing that wrote it" % item_id)
    if not record.get("approved"):
        return False, "not approved yet, and the author cannot approve it"
    approver = record.get("approved_by")
    if review._norm(approver) == review._norm(record.get("author") or author):
        return False, ("approved by its own author, which is not an approval")
    return True, "approved by %s, who did not write it" % approver


def check_has_something_to_say(message):
    body = str(message.get("body") or "").strip()
    if not body:
        return False, "the message is empty"
    return True, "%d characters" % len(body)


CHECKS = [
    ("recipient-identified", check_recipient_is_identified),
    ("not-held", check_not_held),
    ("room-in-shared-limit", check_room_in_the_shared_limit),
    ("independently-approved", check_independently_approved),
    ("has-something-to-say", check_has_something_to_say),
]


def review_outbound(message):
    """Run every check. Returns a verdict; sends nothing, ever.

    A check that raises counts as a refusal. Failing towards refusal is the only
    safe direction: an error in the hold lookup must not be read as "not held".
    """
    results = []
    for cid, fn in CHECKS:
        try:
            ok, reason = fn(message)
        except Exception as err:
            ok, reason = False, ("the check could not run (%s), so this is refused "
                                 "rather than assumed safe" % err)
        results.append({"id": cid, "ok": bool(ok), "reason": reason})

    refusals = [r for r in results if not r["ok"]]
    return {
        "refused": bool(refusals),
        "checks": results,
        "reasons": [r["reason"] for r in refusals],
        "to": message.get("to"),
        "checked": _now(),
        # Repeated here so that anything reading a verdict, in a log or a file,
        # can see that a passing verdict is still not a sent message.
        "sent": False,
        "note": "Nothing was sent. This layer has no way to send.",
    }


def stage_for_you(message, verdict=None):
    """Write a passing message to your outbox for you to send by hand.

    This is as far as the system goes. The file it writes is a note to you, in a
    folder, marked unsent. Something has to carry it the last few inches to a
    person, and that something is you.
    """
    verdict = verdict or review_outbound(message)
    if verdict["refused"]:
        raise ValueError("refused: " + "; ".join(verdict["reasons"]))

    folder = crm_paths.outbox_dir()
    stamp = _now().replace(":", "").replace("-", "")
    name = "".join(c for c in str(message.get("to") or "unknown")
                   if c.isalnum() or c in " -_").strip() or "unknown"
    target = folder / ("%s--%s.md" % (stamp, name))
    body = """---
to: {to}
identifier: {ident}
kind: {kind}
written-by: {author}
approved-by: {approver}
staged: {when}
sent: false
---

# For you to send

Copy this, read it once more, and send it yourself. Nothing here will do it for
you, and nothing here can.

---

{message}

---

Every check passed:

{checks}
""".format(to=message.get("to", ""), ident=message.get("identifier", ""),
           kind=message.get("kind", "message"), author=message.get("author", ""),
           approver=(review.record_for(message.get("item_id")) or {}).get("approved_by", ""),
           when=_now(), message=str(message.get("body", "")).strip(),
           checks="\n".join("- %s: %s" % (c["id"], c["reason"]) for c in verdict["checks"]))
    safe_write.write_text(target, body)
    return target


def explain(verdict):
    """The verdict as text, for printing."""
    out = []
    for c in verdict["checks"]:
        out.append("  %-6s  %-24s %s" % ("ok" if c["ok"] else "REFUSE",
                                         c["id"], c["reason"]))
    out.append("")
    if verdict["refused"]:
        out.append("REFUSED. Nothing was staged and nothing was sent.")
    else:
        out.append("Ready for you. Staged unsent; you send it yourself.")
    return "\n".join(out)


def main(argv):
    """Ask the gate about one person, and watch what it does.

        python sendgate.py "Rowan Ashdown"
        python sendgate.py "https://www.linkedin.com/in/rowanashdown"

    Put somebody on hold with holds.py first, then run this against them. Two
    minutes, and it is the only way to actually trust the thing: you are not
    reading a promise, you are watching a refusal.
    """
    who = argv[1] if len(argv) > 1 else "Somebody Not In Your Records"
    message = {"to": who, "identifier": who if "/" in who else "",
               "kind": "message",
               "body": "A message that is going nowhere, because nothing here sends.",
               "author": "a-writer", "item_id": "gate-demonstration"}
    print("Putting one message through every gate in this layer.")
    print("")
    print("  recipient   %s" % who)
    print("")
    print(explain(review_outbound(message)))
    print("")
    print("Whatever the verdict says, nothing was sent. There is no code in this")
    print("layer that can send. That is what the layer is.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))


# Deliberately absent from this file, and from this repository:
#   send()  deliver()  dispatch()  post()  transmit()
# Adding one is not an improvement to this layer. It is the removal of it.
