"""Test: a hold survives whatever identifier the caller happens to be holding.

What should be true (Layer 6): the per-person hold is the last automatic gate
before a real human being. It must not depend on the part that records the hold
and the part that checks it spelling a name the same way.

Why this needs a test and not a rule in a document: the failure is silent and
looks like success. A check that returns "not held" because it was asked with the
wrong identifier is indistinguishable, in every log, from a check that returned
"not held" because the person genuinely was not held.

Fails the same, never open: the wider check looks at the identifiers it was given
FIRST, and only then goes looking for others. If the people folder is missing or
unreadable, the answer is exactly what the narrow check would have said.

Run:  python tests/test_holds.py
"""

import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))

import crm_paths
import holds

FAILS = []


def check(label, cond, detail=""):
    ok = bool(cond)
    print(("  PASS  " if ok else "  FAIL  ") + label
          + (("   [" + detail + "]") if detail and not ok else ""))
    if not ok:
        FAILS.append(label)


# Never touch a real CRM from a test.
VAULT = Path(tempfile.mkdtemp(prefix="crm-layer6-holds-"))
crm_paths.use_vault(VAULT)

people = VAULT / "People"
people.mkdir(parents=True)
(people / "Mara Quennell.md").write_text(
    "---\nname: \"* Mara Quennell\"\n"
    "linkedin-url: https://www.linkedin.com/in/maraquennell/\n---\n",
    encoding="utf-8")
(people / "Tobias Fenwick.md").write_text(
    "---\nname: Tobias Fenwick\n"
    "linkedin-url: https://www.linkedin.com/in/tobiasfenwick\n---\n",
    encoding="utf-8")

URL = "https://www.linkedin.com/in/maraquennell"

print("\n=== 1. a hold recorded under a name only ===")

holds.hold("Mara Quennell", reason="picked the conversation up by hand")

check("the narrow check misses a caller holding only the link",
      holds.is_held(URL) is False,
      "this is the defect the wider check exists for")
check("the wider check catches it", holds.is_held_person(URL) is True)
check("the wider check still catches the plain name",
      holds.is_held_person("Mara Quennell") is True)
check("and the name with a marker in front of it",
      holds.is_held_person("* Mara Quennell") is True)
check("and a caller passing both, which is what a send path does",
      holds.is_held_person(URL, "Mara Quennell") is True)
check("and the link with tracking parameters on the end",
      holds.is_held_person(URL + "/?trk=something") is True)

print("\n=== 2. nobody is held who should not be ===")

check("an unheld person is not held by link",
      holds.is_held_person("https://www.linkedin.com/in/tobiasfenwick") is False)
check("an unheld person is not held by name",
      holds.is_held_person("Tobias Fenwick") is False)
check("somebody absent from the records entirely is not held",
      holds.is_held_person("https://www.linkedin.com/in/deliamarchetti",
                           "Delia Marchetti") is False)

print("\n=== 3. a hold recorded by link is caught by a name-first caller ===")

holds.hold("https://www.linkedin.com/in/tobiasfenwick", reason="test")
check("name-first check finds a link-keyed hold",
      holds.is_held_person("Tobias Fenwick") is True)

print("\n=== 4. aliases recorded with the hold are matched too ===")

holds.hold("Delia Marchetti", reason="test",
           aliases=["https://www.linkedin.com/in/deliamarchetti"])
check("the alias link is held", holds.is_held("https://www.linkedin.com/in/deliamarchetti") is True)

first_since = holds.hold("Delia Marchetti", reason="test")["held"][holds._key("Delia Marchetti")]["since"]
again = holds.hold("Delia Marchetti", reason="a second, different reason")
entry = again["held"][holds._key("Delia Marchetti")]
check("holding somebody twice keeps the date they were first held",
      entry["since"] == first_since, "%s vs %s" % (entry["since"], first_since))
check("and takes the newer reason", entry["reason"] == "a second, different reason")
check("and does not duplicate the alias", len(entry.get("aliases") or []) == 1,
      str(entry.get("aliases")))

print("\n=== 5. a broken lookup must not release anybody ===")

real = holds.other_identifiers
holds.other_identifiers = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("records unreadable"))
try:
    check("a hold matching what the caller gave still holds",
          holds.is_held_person("Mara Quennell") is True)
    check("and somebody unheld is still not held",
          holds.is_held_person("Somebody Else") is False)
finally:
    holds.other_identifiers = real

print("\n=== 6. release lets one person through, and only one ===")

check("release by an alias works",
      holds.release("https://www.linkedin.com/in/deliamarchetti") is True)
check("that person is no longer held", holds.is_held_person("Delia Marchetti") is False)
check("everybody else is still held", holds.is_held_person("Mara Quennell") is True)
check("releasing somebody who was not held reports so",
      holds.release("Nobody At All") is False)

print("\n=== 7. the hold list cannot be half-written ===")

# The file this layer most needs to survive a crash. An empty hold list quietly
# releases everyone, which is the worst possible failure and the easiest to miss.
holds.hold("Someone Temporary", reason="test")
after = holds.state_path().read_text(encoding="utf-8")
check("the file is still valid after a rewrite", after.strip().endswith("}"))
check("the earlier entries survived the rewrite", "Mara Quennell" in after)
check("no temporary file is left behind",
      not list(holds.state_path().parent.glob("*.tmp")))
check("the state file is inside the CRM, not next to the code",
      str(VAULT) in str(holds.state_path()), str(holds.state_path()))

shutil.rmtree(VAULT, ignore_errors=True)

print("\n%s" % ("ALL PASS" if not FAILS else "FAILURES: " + ", ".join(FAILS)))
sys.exit(1 if FAILS else 0)
