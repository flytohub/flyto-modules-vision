# Package created: `vision.observe`, the gateway, and the observation contract

Owner: claude
Branch: main
Date: 2026-08-08

## What changed

The package exists. It is the second reference implementation of the Flyto2
plugin contract, and the producer flyto-cloud's evidence layer had no answer for
since the Space task loop was built.

- `src/flyto_modules_vision/gateway.py` — reaching a vision gateway on the
  machine the job was dispatched to. The address is configuration
  (`FLYTO_VISION_GATEWAY_URL`); the path is contract.
- `src/flyto_modules_vision/observation.py` — what counts as an observation.
  Structure is refused, vocabulary is forwarded.
- `src/flyto_modules_vision/steps.py` — the one table owning module ids and the
  capability each provides.
- `src/flyto_modules_vision/modules.py` — `vision.observe`, declaring
  `provides_capability` so a host learns what installing this made available.
- `.github/workflows/publish-pypi.yml` — mirrors flyto-core's: Trusted
  Publishing, SLSA provenance, and jobs that test the built wheel as a consumer
  meets it.

## Why

**It never opens a camera.** A step reads what a gateway already observed. Two
reasons: a module that could open a device would be a narrower version of the
authority flyto-core's `shell.*` denylist exists to refuse; and a mission that
could make a lens fire could take pictures until it got one it liked. Reading
state the feed gathered on its own schedule means the evidence is of the room,
not of the asking.

**Reading here, while robotics declares, is the same rule.** The robotics steps
build a plan and hand it to the robot's own runner because flyto-core runs on the
worker and the desktop, never on the robot — the loopback address meaning "this
robot" on a Pi means "this container" on a worker. A vision step reads because
the job was dispatched to the machine holding the camera and the engine is
running there. Same rule, different answer, because the hardware is on this side
of the boundary. The two packages together are what show the contract covers both
geometries; one exemplar cannot.

**Rejected:** shipping `vision.read_code` and `vision.record` as declared but
empty. The evidence layer matches a capability to a producer, so claiming one and
returning nothing turns "escalate to something that can do this" into "dispatch
to something that cannot", and the mission stalls instead of climbing.

## Verified

- `PYTHONPATH=src:. pytest tests/ -q` → **38 passed**, none needing a camera or
  flyto-core.
- Against a real installed flyto-core 2.27.0 in a clean venv, from the built
  wheel: discovered through the entry point, `execute` is a coroutine, the
  engine's own `await run()` path returns a clean refusal when no gateway is
  listening, and `ModuleRegistry.capabilities()` returns
  `{'vision.observe': ['vision.observe']}`.
- Against a live flyto-cloud desktop backend with a real USB camera: four usable
  `zone.overview` observations, 1.2 s old.
- **`usable` must be stated.** Found by an adversarial review and fixed here: the
  parser read absent as true, which is a Python-shaped default on a
  cross-language boundary. Verified by running it — Go's most copy-pasted struct
  tag, `json:"usable,omitempty"` on a bool, emits `{"kind":"zone.overview"}` for
  `Usable: false`; Jackson's `NON_DEFAULT` does the same. A plugin reporting "I
  looked and the view was blocked" would have been read as usable evidence, on
  the field that decides whether a mission counts as proven.

## Not verified

- **Not published to PyPI.** The pending publisher must be created in the PyPI
  account sidebar first; that is an owner action. Nothing has been tagged.
- The publish workflow has never run. Its wheel-consumer jobs are written but
  unexercised.
- No Rust or Go plugin was written against this package's shape, so its claim to
  demonstrate a language-neutral contract rests on the gateway indirection rather
  than on a second-language implementation.
- `vision.read_code` and `vision.record` have no producer anywhere, so the
  evidence kinds needing them cannot yet be satisfied by anything.
