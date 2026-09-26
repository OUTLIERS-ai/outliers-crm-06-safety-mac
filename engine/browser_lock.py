"""
browser_lock.py - one thing drives the browser at a time.

Two automated jobs opening the same browser profile at once is how a logged-in
session gets corrupted. They fight over the same cookies and the same open tabs,
and the failure is not a crash: it is a session that stops being trusted, which
you find out about days later when everything mysteriously needs logging in
again.

The fix is unglamorous. Before anything touches the browser it takes a lock, and
if the lock is already held it does not wait politely and try anyway. It stops
and says who has it.

    import browser_lock
    with browser_lock.held("collector"):
        ...drive the browser...

A lock that can be left behind forever is worse than no lock, because eventually
somebody deletes it by hand and stops trusting locks. So a lock older than the
stale limit is reclaimed automatically, and the reclaim is reported rather than
done quietly.

Needs: Python 3.8 or newer. Nothing else.
"""

import json
import os
import sys
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

import crm_paths

# How long before a lock is assumed to be the wreckage of a crashed job. Long
# enough that a slow legitimate run is never interrupted; short enough that a
# crash does not block the system until somebody notices.
STALE_AFTER_SECONDS = 1800


class Busy(Exception):
    """Raised when something else is already driving the browser."""


def lock_path():
    return crm_paths.state_dir() / "browser.lock"


def _now():
    return datetime.now(timezone.utc)


def _read():
    p = lock_path()
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _age_seconds(info):
    try:
        t = datetime.fromisoformat(str(info.get("taken", "")).replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    if not t.tzinfo:
        t = t.replace(tzinfo=timezone.utc)
    return (_now() - t).total_seconds()


def current():
    """Who holds the lock, or None. Read only."""
    return _read()


def acquire(owner, stale_after=STALE_AFTER_SECONDS):
    """Take the lock. Returns a token to release it with, or raises Busy.

    Deliberately does not wait. A job that queues behind another browser job will
    be holding an out-of-date view of the world by the time it gets in, and it is
    better to run again from scratch later than to run on stale intent.
    """
    path = lock_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex
    payload = json.dumps({"owner": str(owner), "pid": os.getpid(),
                          "token": token, "taken": _now().isoformat(timespec="seconds")},
                         indent=2) + "\n"

    for attempt in (1, 2):
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            info = _read() or {}
            age = _age_seconds(info)
            if attempt == 1 and age is not None and age > stale_after:
                # The holder is long gone. Reclaiming is reported, not silent: a
                # lock that vanishes without explanation teaches people to ignore
                # locks.
                sys.stderr.write(
                    "browser_lock: reclaiming a lock held by %r for %d seconds, "
                    "which is longer than any real run.\n"
                    % (info.get("owner", "something"), int(age)))
                try:
                    os.unlink(str(path))
                except OSError:
                    pass
                continue
            raise Busy("%s is driving the browser (since %s). Nothing else may."
                       % (info.get("owner", "something else"), info.get("taken", "?")))
        else:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(payload)
            return token
    raise Busy("could not take the browser lock")


def release(token):
    """Give the lock back. Only the holder can, so one job cannot free another."""
    info = _read()
    if not info:
        return False
    if info.get("token") != token:
        return False
    try:
        os.unlink(str(lock_path()))
    except OSError:
        return False
    return True


@contextmanager
def held(owner, stale_after=STALE_AFTER_SECONDS):
    """The normal way to use this. Releases even when the body raises."""
    token = acquire(owner, stale_after=stale_after)
    try:
        yield token
    finally:
        release(token)


def main(argv):
    info = current()
    if not info:
        print("The browser is free. Nothing holds the lock.")
        return 0
    age = _age_seconds(info)
    print("held by   %s" % info.get("owner"))
    print("since     %s" % info.get("taken"))
    print("age       %s seconds" % (int(age) if age is not None else "unknown"))
    if age is not None and age > STALE_AFTER_SECONDS:
        print("")
        print("That is longer than any real run. The next job to ask will reclaim it.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
