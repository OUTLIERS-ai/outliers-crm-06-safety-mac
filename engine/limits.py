"""
limits.py - one budget, shared by everything, counted in one place.

The mistake this exists to prevent: giving each activity its own allowance.
Messages get an allowance, connection requests get an allowance, comments get an
allowance, and every one of them stays inside its own limit. Then all three run
on the same day, from the same account, and the total is three times what you
thought you had agreed to. Every part behaved. The whole did not.

So there is one counter. Everything that could be noticed from outside asks the
same counter for room, and the counter does not care which activity is asking.

    import limits
    ok, reason = limits.allow("message", cap=30)
    if not ok:
        stop; reason says why
    limits.record("message")

The count resets when the date changes. Nothing here decides what a safe number
is: you do, when you install the layer, because the safe number depends on your
account, your platform and your history, and a number picked by somebody else is
a guess wearing a uniform.

Needs: Python 3.8 or newer. Nothing else.
"""

import sys
from datetime import date

import crm_paths
import safe_write

# Used only when nobody has said otherwise. Deliberately small: a limit that is
# too low costs you a little reach, a limit that is too high can cost the account.
DEFAULT_CAP = 20


def state_path():
    return crm_paths.state_dir() / "activity.json"


def _today():
    return date.today().isoformat()


def _load():
    data = safe_write.read_json(state_path(), {})
    if not isinstance(data, dict) or data.get("day") != _today():
        return {"day": _today(), "counts": {}}
    data.setdefault("counts", {})
    return data


def counts():
    """What has been done since the count last reset, by kind."""
    return dict(_load()["counts"])


def total():
    """Everything, added together. This is the number the cap applies to."""
    return sum(_load()["counts"].values())


def cap_from_config(default=DEFAULT_CAP):
    """The cap you set when you installed the layer, if it is there."""
    data = safe_write.read_json(crm_paths.vault() / "_layers" / "config.json", {})
    try:
        return int(data.get("daily-cap", default))
    except (TypeError, ValueError):
        return default


def remaining(cap=None):
    cap = cap_from_config() if cap is None else int(cap)
    return max(cap - total(), 0)


def allow(kind, cap=None):
    """May one more thing of any kind happen? Returns (allowed, reason).

    The reason is written for a person reading a log later, not for a machine.
    """
    cap = cap_from_config() if cap is None else int(cap)
    done = total()
    if done >= cap:
        return False, ("the shared daily limit of %d is used up (%s)"
                       % (cap, _breakdown()))
    return True, "%d of %d used so far" % (done, cap)


def _breakdown():
    rows = sorted(counts().items(), key=lambda kv: -kv[1])
    return ", ".join("%s %d" % (k, v) for k, v in rows) or "nothing yet"


def record(kind, note=None):
    """Count one thing that happened. Returns the new total.

    Called AFTER the thing happened, never before. Counting an intention rather
    than an action means a run that stops halfway has already spent budget it
    never used, and the next run behaves as though it did.
    """
    kind = str(kind or "unknown").strip().lower()
    data = _load()
    data["counts"][kind] = data["counts"].get(kind, 0) + 1
    if note:
        data.setdefault("last", {})[kind] = str(note)
    safe_write.write_json(state_path(), data)
    return sum(data["counts"].values())


def reset():
    """Clear the count. For tests, and for the day you decide to start again."""
    safe_write.write_json(state_path(), {"day": _today(), "counts": {}})


def main(argv):
    cap = cap_from_config()
    print("shared daily limit   %d" % cap)
    print("used so far          %d" % total())
    print("left                 %d" % remaining(cap))
    print("")
    print("by activity:")
    for k, v in sorted(counts().items(), key=lambda kv: -kv[1]):
        print("  %-20s %d" % (k, v))
    if not counts():
        print("  (nothing yet)")
    print("")
    print("One counter, shared. Three activities each staying inside their own")
    print("allowance is how a total nobody agreed to gets reached.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
