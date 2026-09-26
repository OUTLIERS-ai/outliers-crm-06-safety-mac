"""
holds.py - stop automation for one person, and carry on with everyone else.

The rule this enforces: if you have picked up a conversation yourself, nothing
automatic should be talking over you. Not paused for everybody, paused for that
one person. Holding three people out of ten holds those three; the other seven
carry on.

This is the enforcement half. Every path that could put something in front of a
person consults it, per recipient, before doing anything:

    import holds
    if holds.is_held_person(profile_url, name):
        skip this person, note why, carry on with the rest

The detection half - a job that notices you have messaged somebody yourself and
calls holds.hold() - is a separate thing and is deliberately not in this file.
Enforcement should not depend on detection working.

TWO THINGS THAT LOOK LIKE DETAILS AND ARE NOT

**A hold has to answer to every identifier.** A hold recorded under a name is
invisible to a caller that only has a profile link, and the other way round. The
person who records the hold and the code that checks it are rarely holding the
same identifier, so the hold stores aliases and matches on any of them.

**A hold has to survive decoration.** Records often carry a marker in front of
the name: a symbol, a tag, an initial. A hold keyed on the bare name must still
catch the decorated one, so leading non-word characters are stripped before
matching. Widening a safety gate always fails in the safe direction: more people
held, never fewer. A leading symbol cannot tell two different people apart, so
nothing is lost by ignoring it.

CLI:
    python _engine/holds.py status
    python _engine/holds.py hold "<link-or-name>" "reason" [other identifier ...]
    python _engine/holds.py release "<link-or-name>"

Needs: Python 3.8 or newer. Nothing else.
"""

import re
import sys
from datetime import datetime, timezone

import crm_paths
import safe_write

# The command a member types to start Python: `python3` on a Mac, which has no plain
# `python` command, and `python` everywhere else, as the Windows guides print it.
PY = "python3" if sys.platform == "darwin" else "python"


def _typed(name):
    """The program `name` (it sits beside this file) as the member types it from the folder
    they are in: `_engine/<name>` from the CRM folder, `<name>` from inside `_engine`."""
    import os
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), name)
    try:
        typed = os.path.relpath(path)
    except ValueError:                      # the member is on another drive
        typed = path
    if typed.startswith(".."):
        typed = path
    typed = typed.replace("\\", "/")
    return '"%s"' % typed if " " in typed else typed


def state_path():
    return crm_paths.state_dir() / "holds.json"


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _key(person):
    """Stable key for one identifier. Links win; otherwise a tidied name."""
    if not person:
        return ""
    s = str(person).strip()
    if "/" in s and ("." in s.split("/")[0] or s.lower().startswith("http")):
        # A link. Drop anything after a question mark and any trailing slash, so
        # the same profile arriving with tracking parameters still matches.
        return s.split("?")[0].rstrip("/").lower()
    s = re.sub(r"\s+", " ", s).strip().lower()
    # Strip leading decoration only. \w is unicode-aware, so accented and
    # non-Latin initials survive; only symbols and punctuation are removed.
    return re.sub(r"^\W+", "", s, flags=re.UNICODE)


def _keys(*identifiers):
    return {k for k in (_key(i) for i in identifiers if i) if k}


def _load():
    data = safe_write.read_json(state_path(), {"held": {}})
    if not isinstance(data, dict) or "held" not in data:
        return {"held": {}}
    return data


def _save(data):
    safe_write.write_json(state_path(), data)


def _entry_keys(store_key, entry):
    """Every identifier one held entry answers to."""
    ids = [store_key, entry.get("person", "")]
    aliases = entry.get("aliases") or []
    ids.extend(aliases if isinstance(aliases, list) else [aliases])
    return _keys(*ids)


def is_held(*identifiers):
    """True if ANY identifier given matches ANY identifier of ANY held entry.

    Pass everything you know about the person: the link and the name, in any
    order. This function matches what it is given, so a link-only check sails
    straight past a hold recorded under a name.
    """
    probe = _keys(*identifiers)
    if not probe:
        return False
    held = _load().get("held", {})
    if probe & set(held.keys()):
        return True
    return any(probe & _entry_keys(k, e) for k, e in held.items())


def is_held_person(*identifiers):
    """is_held(), then a second look using every identifier the records know.

    Why the second look exists: the caller knows the identifiers from its own
    source. A hold recorded from a different source, under a different spelling,
    is invisible to it. So if the direct check finds nothing, the people folder
    is consulted for other identifiers belonging to the same person, and those
    are checked too.

    It fails the SAME, never open. If the people folder is missing, unreadable,
    or does not know this person, the answer is exactly what is_held() would have
    said. Widening can only ever find more holds, never fewer.
    """
    if is_held(*identifiers):
        return True
    try:
        expanded = other_identifiers(*identifiers)
        return bool(expanded) and is_held(*expanded)
    except Exception:
        return False                    # already checked as given, above


def other_identifiers(*identifiers):
    """Every identifier the people folder holds for the same person.

    A deliberately simple reader: one record per person, front matter at the top,
    a name and a link. It looks for a record matching any identifier given, and
    returns every identifier on that record.
    """
    probe = _keys(*identifiers)
    if not probe:
        return []
    # Fields holding one identifier each, and fields that may hold several
    # separated by commas. A name is never split on spaces: doing so would make
    # a record for one person answer to each of their names on its own, which
    # would hold the wrong people.
    WHOLE = ("name", "alias")
    MANY = ("linkedin-url", "profile", "email", "phone", "identifier", "aliases")

    folder = crm_paths.people_dir()
    if not folder.exists():
        return []
    for note in sorted(folder.glob("*.md")):
        found = {_key(note.stem)}
        for line in _front_matter_lines(note):
            field, _, value = line.partition(":")
            field = field.strip().lower()
            value = value.strip().strip('"\'')
            if field in WHOLE:
                found.add(_key(value))
            elif field in MANY:
                for part in value.replace(",", " ").split():
                    found.add(_key(part.strip('"\'')))
        found = {f for f in found if f}
        if probe & found:
            return sorted(found)
    return []


def _front_matter_lines(note):
    """The `key: value` lines between the two marker lines at the top of a record.

    Stopping at the closing marker matters: a sentence in the body that happens
    to contain a colon is not an identifier, and treating it as one would hold
    people who were never held.
    """
    try:
        text = note.read_text(encoding="utf-8", errors="replace")[:4000]
    except OSError:
        return []
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return []
    out = []
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line:
            out.append(line)
    return out


def hold(person, reason="picked up by hand", evidence=None, aliases=None):
    """Hold one person. Running it twice keeps the original date and adds to it."""
    data = _load()
    key = _key(person)
    if not key:
        return data
    entry = data["held"].get(key, {"person": str(person).strip(),
                                   "since": _now(), "evidence": []})
    entry["reason"] = reason
    if evidence:
        entry.setdefault("evidence", [])
        entry["evidence"].extend(evidence if isinstance(evidence, list) else [evidence])
    if aliases:
        alias_list = aliases if isinstance(aliases, list) else [aliases]
        known = _keys(key, *(entry.get("aliases") or []))
        for a in alias_list:
            ak = _key(a)
            if ak and ak not in known:
                entry.setdefault("aliases", []).append(str(a).strip())
                known.add(ak)
    data["held"][key] = entry
    _save(data)
    return data


def release(person):
    """Release by any identifier the entry answers to. Returns True if one went."""
    data = _load()
    probe = _keys(person)
    if not probe:
        return False
    matched = [k for k, e in data.get("held", {}).items() if probe & _entry_keys(k, e)]
    for k in matched:
        del data["held"][k]
    if matched:
        _save(data)
        return True
    return False


def held():
    return list(_load().get("held", {}).values())


def status():
    rows = held()
    return {"count": len(rows), "held": rows}


def main(argv):
    args = argv[1:]
    if not args or args[0] == "status":
        s = status()
        print("%d person(s) held:" % s["count"])
        for e in s["held"]:
            print("  - %s   (%s, since %s)" % (e.get("person"), e.get("reason"),
                                               e.get("since")))
        if not s["held"]:
            print("  (nobody. Automation will consider everyone.)")
    elif args[0] == "hold" and len(args) > 1:
        hold(args[1], args[2] if len(args) > 2 else "picked up by hand",
             aliases=args[3:] or None)
        print("HELD %s. Nothing automatic will reach this person." % args[1])
    elif args[0] == "release" and len(args) > 1:
        print("released %s." % args[1] if release(args[1])
              else "%s was not held." % args[1])
    else:
        print(__doc__.replace("    python _engine/holds.py", "    python " + _typed("holds.py"))
              .replace("    python ", "    %s " % PY))
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
