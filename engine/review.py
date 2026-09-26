"""
review.py - the thing that wrote it does not get to approve it.

You would not mark your own homework, and you would not ask somebody to check
their own work and then act on the answer. The reason is not that people are
dishonest. It is that the same reasoning that produced the mistake is the
reasoning that would have to catch it, and it does not, because to that reasoning
the work looks right.

An assistant has the same problem in a stronger form. Asked to check its own
output it produces a confident review, because reviewing is a writing task and it
is good at writing tasks. The review reads exactly like an independent one.

So approval is recorded, it names who approved, and an approval from the author
is refused. Not discouraged. Refused, by the code, before anything downstream can
treat the item as approved.

    import review
    review.submit("draft-1", author="fit-scorer", summary="a message to Rowan")
    review.approve("draft-1", reviewer="fit-scorer")   -> refused
    review.approve("draft-1", reviewer="you")          -> recorded

Needs: Python 3.8 or newer. Nothing else.
"""

import sys
from datetime import datetime, timezone

import crm_paths
import safe_write


class SelfApproval(Exception):
    """Raised when the author tries to approve their own work."""


def state_path():
    return crm_paths.state_dir() / "review.json"


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _norm(party):
    return " ".join(str(party or "").split()).strip().lower()


def _load():
    data = safe_write.read_json(state_path(), {"items": {}})
    if not isinstance(data, dict) or "items" not in data:
        return {"items": {}}
    return data


def submit(item_id, author, summary="", payload=None):
    """Record that something was produced, and by whom. Returns the record."""
    item_id = str(item_id)
    if not _norm(author):
        raise ValueError("an item with no author cannot be independently reviewed")
    data = _load()
    record = {
        "id": item_id,
        "author": str(author),
        "summary": str(summary),
        "payload": payload or {},
        "written": _now(),
        "approved_by": None,
        "approved": False,
    }
    data["items"][item_id] = record
    safe_write.write_json(state_path(), data)
    return record


def approve(item_id, reviewer):
    """Approve somebody else's work. Raises SelfApproval if it is your own.

    Raising rather than returning False is deliberate. A caller that ignores a
    returned False carries on as though the item were approved; a caller that
    ignores an exception stops.
    """
    item_id = str(item_id)
    data = _load()
    record = data["items"].get(item_id)
    if not record:
        raise KeyError("nothing was submitted under %r" % item_id)
    if not _norm(reviewer):
        raise ValueError("an approval has to name who gave it")
    if _norm(reviewer) == _norm(record.get("author")):
        raise SelfApproval(
            "%r wrote this and cannot approve it. The reasoning that produced the "
            "work is the reasoning that would have to find the fault in it."
            % record.get("author"))
    record["approved_by"] = str(reviewer)
    record["approved"] = True
    record["approved_at"] = _now()
    data["items"][item_id] = record
    safe_write.write_json(state_path(), data)
    return record


def record_for(item_id):
    return _load()["items"].get(str(item_id))


def is_approved(item_id):
    record = record_for(item_id)
    return bool(record and record.get("approved") and record.get("approved_by")
                and _norm(record["approved_by"]) != _norm(record.get("author")))


def waiting():
    """Everything produced and not yet approved by somebody else."""
    return [r for r in _load()["items"].values() if not r.get("approved")]


def main(argv):
    rows = waiting()
    print("%d item(s) waiting for a second pair of eyes:" % len(rows))
    for r in rows:
        print("  %-22s by %-18s %s" % (r["id"], r["author"], r.get("summary", "")))
    if not rows:
        print("  (nothing waiting)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
