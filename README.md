**This is the Mac version.** On Windows, use [outliers-crm-06-safety](https://github.com/OUTLIERS-ai/outliers-crm-06-safety).

# Outliers CRM - Layer 6 - Order and Safety

By now your CRM has assistants in it. They can form a view about a person, and
several of them can be working at the same time. Any one of them could end up
putting something in front of a real human being.

Nothing yet controls the order they run in, how much they collectively do, or
what happens when one of them is wrong.

**Telling them to be careful is not a control.** An assistant told to be careful
will sometimes not be, and the failure arrives as a real message to a real
person. The restriction has to sit in the machinery, where it is a fact about
what the code can do, rather than in the instructions, where it is a hope about
what it will choose.

## The thing to understand before anything else

**Nothing in this layer can send anything.** Not behind a setting, not behind a
flag, not disabled for now. There is no code for it anywhere in this repository,
and one of the tests fails if somebody adds any.

The furthest the system goes is writing a file into your outbox, marked unsent,
telling you to send it yourself. That last few inches is you, permanently.

## Install it

    python3 install.py

One command. It finds the CRM you built in Layer 1 and installs into it. It asks
you two questions:

- **How many messages a day is safe in your world?** Everything counted together,
  not per activity.
- **Who must never be contacted automatically?** Names or links, comma separated.
  They go straight onto the hold list.

## What it needs beneath it

Layer 5. The installer checks and stops politely if it is not there. A safety
layer with nothing to make safe is furniture.

## What it installs

| Path in your CRM | What it does |
|---|---|
| `_engine/holds.py` | Stops automation for one person, and carries on with everyone else. |
| `_engine/limits.py` | One daily budget, shared by every activity. |
| `_engine/browser_lock.py` | One thing drives the browser at a time. |
| `_engine/sequence.py` | Declares what runs first, and stops what depended on a failure. |
| `_engine/review.py` | The thing that wrote it does not get to approve it. |
| `_engine/sendgate.py` | Runs every check and either refuses or hands you a file. |
| `_state/outbox/` | Where messages wait, unsent, for you. |

## The six controls, and why each one exists

**Holds, per person.** If you have picked a conversation up yourself, nothing
automatic should be talking over you. Held for that one person; everybody else
carries on. A hold has to answer to every identifier that person has, because the
part that records the hold and the part that checks it are rarely holding the
same one.

**One shared limit.** Three activities, each with its own allowance, each staying
inside it, all on the same account. Every part behaves and the total is three
times what you agreed to. Nothing in any single log says so. One counter, and
everything asks it.

**One browser driver.** Two automated jobs in the same browser profile fight over
the same session. The damage does not look like a crash; it looks like an account
that stops trusting the login, days later.

**A declared order.** Otherwise the same work gets done twice, and worse, a step
fails and everything after it runs on whatever was there before. The output looks
normal. It is the previous answer with today's date on it.

**Independent approval.** You would not mark your own homework. The reasoning
that produced the mistake is the reasoning that would have to catch it, and to
that reasoning the work looks right.

**The human send gate.** Nothing reaches a person without you, because nothing
here can reach a person at all.

## Prove it to yourself, in two minutes

In Terminal, from your CRM folder (if your CRM is not at `~/CRM`, put your own folder in the `cd` line):

    cd ~/CRM
    python3 _engine/holds.py hold "Someone You Know" "testing the gate"
    python3 _engine/sendgate.py "Someone You Know"

Watch it refuse, and read the reasons. Then:

    python3 _engine/holds.py release "Someone You Know"

This is the only way to actually trust it. You are not reading a promise, you are
watching a refusal.

## Run the tests

From the folder you downloaded:

    cd ~/outliers-crm-06-safety-mac
    python3 tests/test_holds.py
    python3 tests/test_shared_limits_and_browser.py
    python3 tests/test_sequence_and_review.py
    python3 tests/test_send_gate_refuses.py
    python3 tests/test_nothing_can_send.py

Each prints a line per assertion and exits non-zero on any failure. Standard
library only.

Note what is missing from that list: there is no test called "it sends
successfully". There is nothing to test.

## What this layer leaves for the next one

Safe and orderly, and working the queue in the order the queue was built.
Something that arrived an hour ago waits its turn behind a list assembled long
before it. Deciding what deserves your attention now is Layer 7.

This repo is made automatically from outliers-crm-06-safety@8a0c545. To report a problem or suggest a change, use that repo, not this one.
