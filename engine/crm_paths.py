"""
crm_paths.py - where everything in your CRM lives, decided in one place.

Shared by every layer from 6 upward, and identical in each of them, so that
installing a later layer never replaces this file with a narrower version of
itself. If you are changing it, change it everywhere.

When these files are installed they live in `_engine/` inside your CRM folder, so
the CRM is simply the folder above them. Tests point this somewhere else, which
is the only reason the override exists: a test that reads and writes the real CRM
is not a test, it is an accident waiting for the day somebody runs it on a live
machine.

Needs: Python 3.8 or newer. Nothing else.
"""

import json
import os
from pathlib import Path

_OVERRIDE = None


def use_vault(path):
    """Point every module in every layer at a different CRM. Used by the tests."""
    global _OVERRIDE
    _OVERRIDE = Path(path) if path else None
    return vault()


def vault():
    if _OVERRIDE is not None:
        return _OVERRIDE
    env = os.environ.get("OUTLIERS_CRM")
    if env:
        return Path(env).expanduser()
    here = Path(__file__).resolve().parent
    if here.name == "_engine":
        return here.parent
    return Path.home() / "CRM"


def config():
    """Your answers to every installer's questions, as one dictionary."""
    path = vault() / "_layers" / "config.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def state_dir():
    """Where the system keeps its own working state. Not your records."""
    return vault() / "_state"


def people_dir():
    return vault() / "People"


def outbox_dir():
    """Where messages wait, unsent, for you to send by hand."""
    return state_dir() / "outbox"


def ledger_path():
    """The event log: one line per thing that happened.

    Written by Layer 3 and appended to by Layer 4's collectors. Everything above
    them only ever reads it.
    """
    override = config().get("ledger")
    if override:
        p = Path(override)
        return p if p.is_absolute() else (vault() / override)
    return vault() / "_ledger" / "events.jsonl"


def today_page():
    return vault() / "Today.md"


def schema_dir():
    """Where the things you own, and the system never edits, live."""
    return vault() / "_schema"


def reports_dir():
    return vault() / "Reports"
