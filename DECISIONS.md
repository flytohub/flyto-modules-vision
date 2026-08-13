# Decisions

## 2026-08-13 — Source provenance is narrow, open and non-authoritative

An observation may carry `source`, but only as an object with exact keys
`provider` and `source_id`. Both are bounded safe ASCII identifiers and the
provider vocabulary is deliberately open: validating structure here must not
create a domain enum that drifts from producers. The parser makes a fresh copy
and refuses missing, extra, unsafe or unbounded fields.

This provenance says which gateway-owned logical source reported an observation;
it does not prove or expose a device. Pixels, images, frames, device fields and
topics are not forwarded. Observations without `source` remain valid, making the
contract additive. Nothing in this decision creates a full executor loop: the Pi
runner still rejects non-robotics actions such as `vision.observe`.

## 2026-08-11 — Only *unresolvable* flyto-core is swallowed, and where decides it

`register_all` runs inside flyto-core's one plugin-loading loop, so it may not
raise when flyto-core is absent or too old to offer the API: that would take
every other plugin's registration down with it. The first version of that guard
was a bare `except ImportError`, which also swallowed a `ModuleNotFoundError`
raised from *inside* an installed flyto-core — a missing requirement on the
host, a circular import — and reported it as "flyto-core could not be reached".
An engine that is installed and broken then looks exactly like one that was
never installed, and whoever has to fix it is sent to the wrong repository with
the real failure named nowhere.

Narrowing the guard to the exception's `name` is not enough, and this is the
part that is easy to get wrong. A partially initialised package re-importing
its own name raises an error carrying `core.modules.base` — byte for byte the
`name` an uninstalled flyto-core carries. The signal that does separate them is
*where* the exception was raised: an import the machinery could not resolve
leaves only the importing frame and the machinery's own on the traceback, while
a module that was found and then broke leaves its own frame there. So the
boundary requires both — nothing executed, and what failed to resolve is one of
the two names asked for here.

Erring is deliberate in one direction. An exception this cannot classify
travels. A plugin failure that reaches the host is a bad log line; a plugin
failure the host never hears about is a builder that is quietly missing a step
with nothing anywhere saying why.

## 2026-08-11 — Registration is repeated, never remembered

The obvious way to make repeated discovery idempotent is a module-level flag
saying registration already happened. It is wrong, and it passes every test
that only ever registers once.

Hosts clear and re-register: flyto-core's own closed-loop verifier calls
`clear()` before `discover_plugins()`, and a hot reload does the same. A plugin
that remembered would make the second discovery a no-op and leave the builder
permanently empty. So `register_all` rebuilds and re-registers on every call,
which is idempotent for the reason that actually holds — the module ids and
their metadata are fixed, so registering twice writes the same entries twice
rather than adding a second set.

For the same reason the package never names itself to the registry. The host
assigns ownership around the entry point call, and a plugin that supplied its
own name could claim another's modules.

## 2026-08-09 — The closed loop is proven against the wheel, and says what it cannot prove

The first recorded real run named a verifier and a probe that were not in the
repository. A record nobody can re-run ages into a claim, so the verifier now
lives here and its own SHA-256 goes into every report it writes. There is no
second probe file: a helper's digest would have to be recorded separately to
mean anything, so the live part is a private flag on the one file the report
names.

What it runs is the **installed wheel**, not the working tree — the child's
`PYTHONPATH` is replaced and `PYTHONSAFEPATH` is set, because a verifier that
imported `src/` would prove the author's files work and say nothing about what a
user receives.

And a pass is stated narrowly, in the report itself: it proves the configured
gateway reported this, through flyto-core's public registry. It does not prove
which camera answered, or that one exists. That limit is inherent, not an
omission — the package holds no device handle it could use to check, which is
the same decision as the one below.

## 2026-08-08 — This package never captures

A step reads what a gateway already observed rather than opening a camera.

Two reasons. **Authority:** flyto-core's module policy denies `shell.*` because
arbitrary host execution from a dispatched job is exactly what it exists to
stop, and a module that could open a device would be a narrower version of the
same authority. Reading a gateway's already-taken observation grants nothing.
**Truth:** a mission that could make a lens fire could take a picture until it
got one it liked. Reading state the feed gathered on its own schedule means the
evidence is of the room, not of the asking.

## 2026-08-08 — The gateway address is configuration, not a parameter

Restores the rule the sibling robotics package guards with a test, and which
the interim approach broke: before this package, an authored command reached
the gateway with a generic `http.get` whose URL lived in operator data. Two
rooms with identical hardware needed two different workflows, and moving the
backend to another port meant editing every template that had ever named it.

It is also what makes the robot's own camera a setting rather than a rewrite:
the same authored step asks the robot's gateway when dispatched to the robot,
and the room's when dispatched to the desktop.

## 2026-08-08 — Reading here, declaring in robotics, is the same rule

The robotics steps declare a plan and hand it to the robot's own runner because
flyto-core runs on the worker and the desktop, never on the robot — the loopback
address meaning "this robot" on a Pi means "this container" on a worker. A
vision step reads because the job was dispatched to the machine holding the
camera and flyto-core is running there.

Same rule — talk to hardware only from the machine that has it — reaching a
different answer because the hardware is on this side of the boundary. The two
packages together are what show the plugin contract covers both geometries.

## 2026-08-08 — Structure is validated, vocabulary is not

A generic fetch reports a 404 page, a login redirect or an empty object as a
successful step, and the mission then goes unsatisfied with nothing saying why.
So malformed answers are refused here.

But whether `zone.overview` is a kind this build knows is flyto-cloud's
question, and it already names an unrecognised kind on the task's own timeline
where an operator is looking. Copying that list here would create a second copy
to drift, and a step that silently dropped a kind the cloud would have accepted
is worse than one that passes it along to be named.

## 2026-08-08 — One module, not three

`vision.read_code` and `vision.record` are the other two capabilities
flyto-cloud's `PRODUCED_BY` names. Both are absent deliberately.

Declaring them would make a gap look filled: the evidence layer matches a
capability to a producer, so a module that claims one and returns nothing turns
"escalate to something that can do this" into "dispatch to something that
cannot", and the mission stalls instead of climbing the ladder. They belong here
when something can actually perform them.
