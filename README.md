# flyto-modules-vision

Optional camera-observation modules for [Flyto2](https://flyto2.com) workflows.

A Flyto2 mission can be required to *show* something, not merely to have run.
This package adds the step that answers "what can be seen here right now" — and
nothing else. It never opens a camera.

```bash
pip install flyto-modules-vision
```

Installing it is the whole decision. flyto-core discovers the package through
its `flyto.modules` entry point, and the builder gains `vision.observe`. Without
it, a mission that needs to see something has nothing to ask.

## What a step does

It asks a vision gateway on the machine the job was dispatched to what that
machine's camera last made out, and returns it as evidence:

```json
{
  "evidence": [
    {"kind": "zone.overview", "zone": "bay", "usable": true,
     "detail": "bay: view_ok (1.2s ago, mean 141, spread 15)"}
  ],
  "observed": 4, "zone": "bay", "usable": 1
}
```

Declare the step's output as `evidence` and flyto-cloud's evidence layer reads
it from the job's variables, the same path every other output already takes.

| Parameter | Meaning | Default |
|---|---|---|
| `zone` | Report only this zone. A mission about the loading bay must not be answered by a clear view of the corridor. | all zones |

## Configuration

| Variable | Meaning | Default |
|---|---|---|
| `FLYTO_VISION_GATEWAY_URL` | Where the gateway is | `http://127.0.0.1:9000` |

**The address is configuration, never a step parameter.** A workflow carrying a
host is bound to one machine — the duplication the capability model exists to
remove, wearing a URL instead of a device id. It is also what makes the robot's
own camera a setting rather than a rewrite: the same authored step asks the
robot's gateway when dispatched to the robot, and the room's when dispatched to
the desktop. A test asserts no parameter can name a host; do not weaken it.

## What it deliberately does not do

**It does not capture.** It reads what a gateway already observed, so a mission
cannot make a lens fire by asking twice, and a package that cannot capture
cannot be talked into capturing.

**It does not decode pixels.** No image library, no HTTP client — the standard
library only, so it installs anywhere the engine does and adds nothing to the
desktop build.

**It does not know the evidence vocabulary.** Malformed answers are refused;
unfamiliar ones are forwarded. Whether `zone.overview` is a kind this build
knows is flyto-cloud's question, and it already names an unrecognised kind on
the task's own timeline. A second copy of that list here would drift.

**It ships one module, not three.** `vision.read_code` and `vision.record` are
the other capabilities flyto-cloud's evidence layer names, and both belong here
when something can actually perform them. Declaring them now would make a gap
look filled: the evidence layer would match a capability to a module that
returns nothing, and the mission would stall instead of escalating to something
that could really do it.

## Verification

```bash
PYTHONPATH=src:. python -m pytest tests/ -q
```

35 tests, none needing a camera or flyto-core.

## Licence

Apache-2.0
