"""Test: there is no way to send anything from this layer, and there never was.

What should be true (Layer 6): the human send gate is absolute. Not a setting,
not a flag, not a confirmation prompt. There is no code here that puts anything
in front of another person, and this test is what keeps it that way when
somebody, later, thinks they are being helpful.

This is a structural test rather than a behavioural one. It reads the source of
every file in this repository and refuses anything that could reach the outside
world: a network library, a browser driver, a mail library, a subprocess, or a
function whose name says it delivers something.

Why a test and not a note in the README: a note is read once by the person who
already agreed with it. This runs every time.

Run:  python tests/test_nothing_can_send.py
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))

import sendgate

FAILS = []


def check(label, cond, detail=""):
    ok = bool(cond)
    print(("  PASS  " if ok else "  FAIL  ") + label
          + (("   [" + detail + "]") if detail and not ok else ""))
    if not ok:
        FAILS.append(label)


# Anything that could carry a message off this machine.
FORBIDDEN_IMPORTS = [
    "requests", "urllib.request", "urllib3", "http.client", "httpx", "aiohttp",
    "socket", "smtplib", "email.message", "ftplib", "telnetlib",
    "playwright", "selenium", "pyppeteer", "webbrowser",
    "subprocess", "os.system", "pty",
]

# Function names that promise delivery. Naming one of these in this layer means
# somebody has started building the thing the layer exists to prevent.
FORBIDDEN_DEFS = re.compile(
    r"^\s*def\s+(send|sends|send_\w+|deliver\w*|dispatch\w*|transmit\w*|"
    r"post_message\w*|publish\w*|submit_to\w*)\s*\(", re.M)

PY_FILES = sorted(list(ROOT.glob("*.py")) + list((ROOT / "engine").glob("*.py")))

print("\n=== 1. the repository has code in it to check ===")

check("there are python files to inspect", len(PY_FILES) >= 5, str(len(PY_FILES)))
check("the gate itself is among them",
      any(f.name == "sendgate.py" for f in PY_FILES))

print("\n=== 2. nothing here can reach the outside world ===")

for f in PY_FILES:
    src = f.read_text(encoding="utf-8", errors="replace")
    code = "\n".join(l for l in src.splitlines() if not l.strip().startswith("#"))
    hits = []
    for name in FORBIDDEN_IMPORTS:
        pattern = r"(?m)^\s*(?:import|from)\s+%s\b" % re.escape(name.split(".")[0])
        if name.count(".") and name in code:
            hits.append(name)
        elif re.search(pattern, code) and name.split(".")[0] == name:
            hits.append(name)
    check("%s imports nothing that could reach a person" % f.name, not hits,
          ", ".join(hits))

print("\n=== 3. no function here claims to deliver anything ===")

for f in PY_FILES:
    src = f.read_text(encoding="utf-8", errors="replace")
    found = FORBIDDEN_DEFS.findall(src)
    check("%s defines no sending function" % f.name, not found, ", ".join(found))

print("\n=== 4. the gate says so about itself, and means it ===")

check("the gate declares that it cannot send", sendgate.CAN_SEND is False)
check("there is no send function on the module",
      not any(hasattr(sendgate, n) for n in
              ("send", "deliver", "dispatch", "transmit", "post")),
      "the absence of the function is the guarantee")

names = [n for n in dir(sendgate) if not n.startswith("_")]
check("the only thing it produces is a verdict or a staged file",
      "review_outbound" in names and "stage_for_you" in names, str(names))

print("\n=== 5. the best outcome is still an unsent file ===")

src = (ROOT / "engine" / "sendgate.py").read_text(encoding="utf-8")
check("every verdict carries sent: False", '"sent": False' in src)
check("the staged file is written with sent: false", "sent: false" in src)
check("the file tells the reader to send it themselves",
      "send it yourself" in src.lower())

print("\n=== 6. no file here opens a browser or drives a session ===")

for f in PY_FILES:
    src = f.read_text(encoding="utf-8", errors="replace").lower()
    code = "\n".join(l for l in src.splitlines() if not l.strip().startswith("#"))
    driving = [w for w in ("new_page(", "goto(", "click(", "type(", "fill(",
                           "sendkeys", "chromedriver")
               if w in code]
    check("%s does not drive a browser" % f.name, not driving, ", ".join(driving))

print("\n=== 7. the browser lock is a lock, not a driver ===")

lock_src = (ROOT / "engine" / "browser_lock.py").read_text(encoding="utf-8")
check("it manages a file and nothing else",
      "os.open" in lock_src and "import json" in lock_src)
check("it never opens a browser", "browser(" not in lock_src.lower())

print("\n%s" % ("ALL PASS" if not FAILS else "FAILURES: " + ", ".join(FAILS)))
sys.exit(1 if FAILS else 0)
