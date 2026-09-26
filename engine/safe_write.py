"""
safe_write.py - write a file without ever damaging the one already there.

Opening a file for writing empties it immediately, before a single byte of the
new content has been written. If anything goes wrong between that moment and the
end of the write, the old content is gone and there is no copy of it.

So nothing in this layer writes to a file directly. It writes to a temporary file
beside the target and then swaps the two in one step, which the operating system
guarantees is all-or-nothing. The worst case becomes a slightly stale file
instead of an empty one.

This matters most for the files in this layer specifically. The hold list is the
last thing standing between an automated system and a person you have taken a
conversation over with. An empty hold list quietly releases everybody.

Needs: Python 3.8 or newer. Nothing else.
"""

import json
import os
from pathlib import Path


def write_text(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(content)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)
    return path


def write_json(path, data):
    return write_text(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def read_json(path, default=None):
    """Read a JSON file, returning the default if it is missing or unreadable.

    A corrupt state file must not stop the system starting. It should, however,
    fail in the safe direction, which is the caller's business: the hold list
    reads back an empty structure and every other check still runs.
    """
    path = Path(path)
    if not path.exists():
        return {} if default is None else default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {} if default is None else default
