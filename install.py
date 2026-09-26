"""
Outliers CRM - Layer 6 - Order and Safety

Your CRM can now form a view. Several assistants can be working at once, and any
one of them could end up putting something in front of a real human being. This
layer installs the control that does not depend on them behaving well.

    python install.py

It finds the CRM you built in Layer 1, asks you two questions, and installs the
layer into it.

Nothing in this layer can send anything. That is not a setting. There is no code
for it, anywhere in here, and the tests refuse to pass if somebody adds any.

Nothing here costs money and nothing leaves your computer.

Needs: Python 3.8 or newer. Nothing else.
"""

import json
import os
import sys
from datetime import date
from pathlib import Path

# The command a member types to start Python: `python3` on a Mac, which has no plain
# `python` command, and `python` everywhere else, as the Windows guides print it.
PY = "python3" if sys.platform == "darwin" else "python"

# The key a member presses. A Mac keyboard's key is Return; Windows keeps Enter, exactly as before
# (Mac build plan V3, wave s1: the Session 7 ruling on the words installers print).
KEY = "Return" if sys.platform == "darwin" else "Enter"

LAYER = 6
LAYER_NAME = "Order and Safety"
NEEDS_LAYER = 5

HERE = Path(__file__).resolve().parent

MODULES = ["crm_paths.py", "safe_write.py", "holds.py", "limits.py",
           "browser_lock.py", "sequence.py", "review.py", "sendgate.py"]

# ---------------------------------------------------------------- small helpers

# No colour codes anywhere. Plenty of terminals print them as literal gibberish
# and a member's first minute with this must not look broken. Plain text works
# everywhere, which is the whole point of the exercise.
BOLD = DIM = OFF = ""


def say(msg=""):
    print(msg, flush=True)


def ask(question, default=None, helptext=None):
    """One plain question. Enter accepts the default."""
    say()
    say(BOLD + question + OFF)
    if helptext:
        say(DIM + "  " + helptext + OFF)
    prompt = "  > " if default is None else "  [%s] > " % default
    try:
        answer = input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        say("\nStopped. Nothing was changed.")
        sys.exit(1)
    return answer or (default or "")


def ask_yes(question, default=True):
    d = "Y/n" if default else "y/N"
    a = ask(question, default=d).strip().lower()
    if a in ("y/n", "y/n".upper(), "y", "yes"):
        return True if a != "y/n" else default
    if a in ("n", "no"):
        return False
    return default


def write(path, content):
    """Write a file without ever damaging one that already exists.

    Writes to a temporary file first, then swaps it into place in a single step.
    If anything goes wrong halfway through, the original is untouched.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(content)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def copy_in(src, dst):
    write(dst, Path(src).read_text(encoding="utf-8"))


def keep_cache_out_of_history(home):
    """Python leaves compiled cache folders beside any code it runs.

    They are noise, they change constantly, and they do not belong in the history
    of your records. Adding two lines to the ignore file costs nothing and saves a
    confusing first look at what changed.
    """
    path = Path(home) / ".gitignore"
    try:
        current = path.read_text(encoding="utf-8") if path.exists() else ""
    except OSError:
        return
    if "__pycache__" in current:
        return
    head = (current.rstrip() + "\n\n") if current.strip() else ""
    write(path, head
          + "# Python leaves these beside any code it runs. Not part of your CRM.\n"
          + "__pycache__/\n"
          + "*.pyc\n")


# -------------------------------------------------------------- finding the CRM

def config_path(home):
    return Path(home) / "_layers" / "config.json"


def looks_like_a_crm(home):
    try:
        return config_path(home).exists()
    except OSError:
        return False


def find_vault():
    """Find the CRM Layer 1 built, by looking for its config file."""
    tried = []
    env = os.environ.get("OUTLIERS_CRM")
    if env:
        tried.append(Path(env).expanduser())
    # Layer 1 leaves a pointer naming wherever the member chose to put their CRM.
    # Without checking it, anyone who declined the default folder is told they have
    # not done Layer 1 when they have, which reads as the series being broken.
    pointer = Path.home() / ".outliers-crm"
    if pointer.exists():
        try:
            noted = pointer.read_text(encoding="utf-8").strip()
            if noted:
                tried.append(Path(noted))
        except OSError:
            pass
    tried.append(Path.home() / "CRM")
    here = Path.cwd()
    tried.append(here)
    tried.extend(here.parents)

    for candidate in tried:
        if looks_like_a_crm(candidate):
            return Path(candidate)

    say()
    say("  Could not find your CRM automatically.")
    raw = ask("Where is it?",
              default=str(Path.home() / "CRM"),
              helptext="The folder Layer 1 built. It has a _layers folder inside it.")
    candidate = Path(raw.strip().strip('"').strip("'")).expanduser()
    return candidate if looks_like_a_crm(candidate) else None


def load_config(home):
    try:
        return json.loads(config_path(home).read_text(encoding="utf-8"))
    except Exception:
        return {}


def refuse_politely(reason):
    say()
    say("=" * 66)
    say("  Not yet.")
    say("=" * 66)
    say()
    say("  " + reason)
    say()
    return 1


# ------------------------------------------------------------------ the interview

def interview(cfg):
    say()
    say("=" * 66)
    say("  OUTLIERS CRM   LAYER %d   %s" % (LAYER, LAYER_NAME.upper()))
    say("=" * 66)
    say()
    say("  You have assistants that can form a view. Nothing yet controls what")
    say("  order they run in, how much they collectively do, or what happens")
    say("  when one of them is wrong.")
    say()
    say("  Telling an assistant to be careful is not a control. One told to be")
    say("  careful will sometimes not be. The restriction has to sit in the")
    say("  machinery, where it is a fact about what the code can do.")
    say()
    say(DIM + "  Two questions. Press %s to accept anything in [brackets]." % KEY + OFF)

    raw_cap = ask("How many messages a day is safe in your world?",
                  default="20",
                  helptext="Everything counted together, not per activity. If you "
                           "are unsure, pick a number lower than you think, because "
                           "too low costs a little reach and too high can cost the "
                           "account.")
    try:
        cap = max(int("".join(c for c in raw_cap if c.isdigit()) or "20"), 1)
    except ValueError:
        cap = 20

    never = ask("Who must never be contacted automatically?",
                default="",
                helptext="Names or profile links, separated by commas. Friends, "
                         "family, anyone you have taken a conversation over with. "
                         "You can add more later, and you will.")

    return {
        "cap": cap,
        "never": [n.strip() for n in never.replace(";", ",").split(",") if n.strip()],
    }


# ------------------------------------------------------------------ what we build

def readme(answers, cfg):
    w = cfg.get("people_word", "contacts")
    return """# Order and safety

**The one thing to understand.** Nothing in this layer can send anything. Not
behind a setting, not behind a confirmation, not disabled for now. There is no
code for it. The best this layer can do is put a file in `_state/outbox/`, marked
unsent, telling you to send it yourself.

That is a stronger guarantee than a rule saying it must not, because a rule is a
hope about what something will choose and this is a fact about what it can do.

## What is in here

| Path | What it does |
|---|---|
| `_engine/holds.py` | Stops automation for one person, and carries on with everyone else. |
| `_engine/limits.py` | One daily budget, shared by every activity. |
| `_engine/browser_lock.py` | One thing drives the browser at a time. |
| `_engine/sequence.py` | Declares the order, and stops what depended on a failure. |
| `_engine/review.py` | The thing that wrote it does not get to approve it. |
| `_engine/sendgate.py` | Runs every check above and refuses, or hands you a file. |
| `_state/` | Where the hold list, the count and the outbox live. |

## The two-minute check that makes it real

Put someone on hold:

    {py} _engine/holds.py hold "Their Name" "picked it up myself"

Then ask the gate about them:

    {py} _engine/sendgate.py "Their Name"

Watch it refuse. You are not reading a promise, you are watching a refusal, and
that is the difference between trusting the system and hoping about it.

Release them again when you want to:

    {py} _engine/holds.py release "Their Name"

## Why the limit is shared

Three activities, each with its own allowance, each staying inside it, all
running on the same account. Every part behaves. The total is three times what
you agreed to, and there is nothing in any single log to notice. So there is one
counter, and everything asks the same one.

    {py} _engine/limits.py

## Why the writer never approves its own work

You would not mark your own homework. The reason is not dishonesty: it is that
the reasoning that produced the mistake is the reasoning that would have to catch
it, and to that reasoning the work looks right. An assistant has this in a
stronger form, because reviewing is a writing task and it is good at writing
tasks. Its review of its own work reads exactly like an independent one.

## Your {w}

Nothing here writes to them. This layer only ever reads the people folder, and
only to work out whether somebody is held.
""".format(w=w, py=PY)


def layer_note(answers, cfg):
    return """# Layer {n} - {name}

**What it built.** A per-person hold list. One daily budget shared by everything.
A lock so only one thing drives the browser. A declared order of steps, with a
rule that nothing downstream of a failure runs. An approval that has to come from
somebody other than the author. And one gate that runs all of them.

**What it does.** It puts the restrictions in the machinery instead of in the
instructions. An assistant told to be careful will sometimes not be. Code that
has no way to send cannot send on the day it misjudges something.

**The idea worth keeping.** The last gate is your hand. Nothing here reaches a
person without you, because nothing here can reach a person at all. The best
outcome the system can produce is a file waiting for you, marked unsent.

**What it leaves for Layer {nxt}.** All of this is safe and orderly, and it works
the queue in the order the queue was built. Something that arrived an hour ago
waits its turn behind a list assembled long before it. Deciding what deserves
your attention now, rather than what was written down first, is the next layer.
""".format(n=LAYER, name=LAYER_NAME, nxt=LAYER + 1)


def build(home, answers, cfg):
    say()
    say("Installing Layer %d into %s" % (LAYER, home))
    say()

    def note(path, what):
        say("  built  %-34s %s" % (str(Path(path).relative_to(home)), what))

    for name in MODULES:
        p = home / "_engine" / name
        copy_in(HERE / "engine" / name, p)
    say("  built  %-34s %s" % ("_engine/ (%d files)" % len(MODULES),
                               "holds, limits, the lock, order, review, the gate"))

    (home / "_state").mkdir(parents=True, exist_ok=True)
    (home / "_state" / "outbox").mkdir(parents=True, exist_ok=True)
    say("  built  %-34s %s" % ("_state/outbox/",
                               "where messages wait for you to send them"))

    p = home / "_state" / "outbox" / "README.md"
    if not p.exists():
        write(p, "# Your outbox\n\n"
                 "Everything in here has passed every check and has NOT been sent.\n"
                 "Nothing in this system can send it. Read each one, then send it\n"
                 "yourself, from wherever you normally would.\n\n"
                 "That last step being yours is the whole point of Layer 6.\n")

    p = home / "_safety" / "README.md"
    write(p, readme(answers, cfg))
    note(p, "what this layer is and how to prove it works")

    p = home / "_layers" / ("Layer %d - %s.md" % (LAYER, LAYER_NAME))
    write(p, layer_note(answers, cfg))
    note(p, "what this layer did, for when you forget")

    # Seed the hold list with the people they just named. Done through the module
    # rather than by writing the file directly, so the identifiers are normalised
    # exactly as every later check will normalise them.
    #
    # Each name is looked up in the records first, and every other identifier
    # found there is attached to the hold. A hold recorded under a bare name is
    # invisible to anything holding only a link, so attaching what is already
    # known costs nothing here and closes the gap before it can open.
    held_count = 0
    if answers["never"]:
        sys.path.insert(0, str(home / "_engine"))
        import crm_paths
        import holds
        crm_paths.use_vault(home)
        for who in answers["never"]:
            if holds.is_held_person(who):
                continue                  # already covered, often by another entry
            others = [i for i in holds.other_identifiers(who) if i != who]
            holds.hold(who,
                       reason="you said never automatically, when you installed this",
                       aliases=others or None)
            held_count += 1
        say("  built  %-34s %s" % ("_state/holds.json",
                                   "%d person(s) held from the start" % held_count))

    keep_cache_out_of_history(home)

    cfg["layer"] = max(int(cfg.get("layer", 0) or 0), LAYER)
    cfg["daily-cap"] = answers["cap"]
    cfg["layer-%d-installed" % LAYER] = date.today().isoformat()
    write(config_path(home), json.dumps(cfg, indent=2) + "\n")
    return held_count


def finish(home, answers, cfg, held_count):
    say()
    say("=" * 66)
    say("  Done. Your CRM now refuses things.")
    say("=" * 66)
    say()
    say("  Shared daily limit:  %d, counting everything together" % answers["cap"])
    say("  Held from the start: %d person(s)" % held_count)
    say()
    say("  Prove it to yourself. From inside %s:" % home)
    say()
    say("      %s _engine/holds.py hold \"Someone You Know\" \"testing\"" % PY)
    say("      %s _engine/sendgate.py \"Someone You Know\"" % PY)
    say()
    say("  Watch it refuse. Two minutes, and it is the only way to actually")
    say("  trust the thing: you are not reading a promise, you are watching a")
    say("  refusal. Release them again with:")
    say()
    say("      %s _engine/holds.py release \"Someone You Know\"" % PY)
    say()
    say("  One thing worth being clear about: nothing installed here can send")
    say("  anything. Not behind a setting, not behind a confirmation. There is")
    say("  no code for it. The furthest the system goes is putting a file in")
    say("  _state/outbox for you, marked unsent.")
    say()


def main():
    home = find_vault()
    if not home:
        return refuse_politely(
            "Layer %d needs Layer 1 first. Run that one and come back." % LAYER)

    cfg = load_config(home)
    have = int(cfg.get("layer", 0) or 0)
    if have < NEEDS_LAYER:
        return refuse_politely(
            "Layer %d needs Layer %d first. Run that one and come back.\n\n"
            "  Your CRM at %s is on Layer %d."
            % (LAYER, NEEDS_LAYER, home, have))

    answers = interview(cfg)
    say()
    say("  Installing into:     %s" % home)
    say("  Shared daily limit:  %d" % answers["cap"])
    say("  Never automatically: %s"
        % (", ".join(answers["never"]) if answers["never"] else "(nobody yet)"))
    if not ask_yes("Go ahead?", default=True):
        say("\nStopped. Nothing was changed.")
        return 1
    held_count = build(home, answers, cfg)
    finish(home, answers, cfg, held_count)
    return 0


if __name__ == "__main__":
    sys.exit(main())
