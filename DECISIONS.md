# Decisions

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
