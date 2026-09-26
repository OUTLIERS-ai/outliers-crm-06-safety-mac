# What I stole

None of these controls are new. Every one is a pattern from a field where getting
it wrong was expensive enough that somebody wrote the rule down. Naming the
originals honestly is useful twice: they are worth reading, and knowing where a
pattern came from tells you the conditions under which it stops working.

## The lock file

**From:** the PID file and the lock file, as old as multi-user Unix. Also the
advisory lock in every database that ever had two clients.

**Why it is here:** two processes with the same resource open is the oldest
concurrency bug there is, and browser sessions are a particularly nasty case
because the damage is not a crash. It is a session that stops being trusted,
discovered days later.

**What was adapted:** the stale-lock reclaim. A pure lock file can be left behind
by a crash and block everything until somebody deletes it by hand, which teaches
people to delete lock files, which is the end of locking. So a lock older than
any plausible run is reclaimed, and the reclaim is announced rather than done
quietly.

## One shared budget rather than a budget per activity

**From:** rate limiting as practised by anyone running against somebody else's
service, and, more usefully, the token bucket. Also from the way an airline
counts total weight rather than weight per passenger.

**Why it is here:** the failure is that every component is individually
compliant. Nothing in any single log looks wrong, which is why per-activity
limits survive so long before anybody notices what the sum is doing.

## The writer never approves its own work

**From:** separation of duties in accounting, where the person who raises an
invoice is not the person who pays it. Also code review, and the reason a test
that edits the code to make itself pass is not a test.

**Why it is here:** the argument transfers exactly and gets stronger with an
assistant. Asked to check its own output it produces a confident review, because
reviewing is a writing task and it is good at writing tasks. The review reads
identically to an independent one.

## The declared order with dependencies

**From:** make, and everything descended from it. Topological sorting, which is
the standard answer to "what order do these things go in", and the reason build
systems refuse a circular dependency rather than looping forever.

**Why it is here:** without it a failure part-way through is invisible. Later
steps run on whatever was there before and produce output that looks completely
normal.

**What was adapted:** an unrelated step still runs when something else fails.
Build systems usually stop everything, which is correct for a build and wrong
here, because refusing to do the tidying because the scoring failed is its own
kind of breakage.

## Fail closed, never open

**From:** safety engineering, where it is called fail-safe design, and from
firewall practice, where the default rule is deny.

**Why it is here:** the tempting behaviour when a check errors is to carry on,
because the check "did not say no". So every check that raises is counted as a
refusal, and the refusal says it refused because it could not check, rather than
because it found something.

## Widening a gate only in the safe direction

**From:** the general principle behind conservative approximation in static
analysis: when you cannot be certain, err towards the answer whose mistakes are
cheap.

**Why it is here:** matching a held person more loosely can hold somebody who did
not need holding, which costs a message. Matching too tightly lets an automated
system talk over a conversation you took on yourself, which costs a
relationship. The two mistakes are not the same size, so the matching is
deliberately loose.

## The outbox

**From:** the drafts folder, and the print spooler. Both exist because the moment
of production and the moment of delivery are different decisions.

**Why it is here:** it is the shape the human send gate takes. The system needs
somewhere to put finished work that is not "sent", and the folder makes the
separation physical rather than conceptual. A file in a folder marked unsent
cannot quietly become a sent message.

## The atomic write

**From:** write-to-temporary-then-rename, which is how every editor, database and
package manager avoids destroying your file when the power goes out.

**Why it is here:** opening a file for writing empties it immediately. The hold
list is the file this matters most for, because an empty hold list does not look
broken. It looks like nobody is held, and it quietly releases everyone.

## A structural test rather than a policy

**From:** the architecture test, sometimes called a fitness function: a test that
asserts something about the shape of the code rather than its behaviour.

**Why it is here:** "we do not send from this layer" written in a README is read
once, by the person who already agreed with it. The same statement as a test that
scans every file for network libraries and delivery-shaped function names runs
every time, including on the day somebody helpful decides an automatic send would
be convenient.
