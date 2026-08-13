# Architecture

```
flyto-core (engine)
  └─ discover_plugins() → flyto.modules entry point → register_all()
       └─ modules.py: vision.observe
            ├─ gateway.py     where to ask (configuration, never a parameter)
            └─ observation.py what counts as an answer
```

## Module boundaries

| Module | Knows about | Does not know about |
|---|---|---|
| `gateway` | an address, a path, HTTP failures | evidence, kinds, zones |
| `observation` | the shape of an observation and bounded source provenance | HTTP, pixels, device identity |
| `steps` | module ids and the capability each provides | everything else |
| `modules` | flyto-core's module contract | how to reach a camera |

`gateway` and `observation` are importable and testable with no flyto-core
present. flyto-core is imported inside `register_all` and `build_modules`,
never at module scope.

Optional `source` provenance crosses this boundary only as exact `provider` and
`source_id` safe ASCII identifiers. Provider vocabulary remains open. The parser
copies that object and drops all outer pixel, image, frame, device and topic
fields; it does not convert provenance into authority over a camera.

## The discovery boundary

`register_all` is called by flyto-core inside the loop that loads every plugin,
so what it does with a failure decides what the host can report about *all* of
them. It swallows exactly one thing: the two flyto-core names it asks for by
hand being unresolvable, or resolvable and not offering the API. Everything
else — a dependency flyto-core itself cannot import, a module of this package
that will not load, a decorator that refuses, a class that cannot be built —
travels, because flyto-core's discovery boundary is the only place an operator
will ever see it named.

The two are not separable by exception type, and often not by the exception's
`name` either: a partially initialised flyto-core raises errors naming
`core.modules.base` exactly as an uninstalled one does. What separates them is
*where* the exception was raised. An unresolvable import leaves only the
importing frame and the machinery's own on the traceback; a module that was
found and broke while running leaves its own frame there. `register_all` reads
that, and requires the resolution failure to name the module it actually asked
for.

Nothing about registration is cached. The host calls `register_all` on every
discovery and it registers every time, so a registry that was cleared or hot
reloaded gets the same set back. Ownership of the registered modules is
assigned by the host around that call; this package never claims it.

## Runtime shape

A step runs inside flyto-core, on the machine the job was dispatched to. The
gateway is on that machine's loopback.

This is the opposite geometry from flyto-modules-robotics, and deliberately so.
The robotics steps *declare* rather than drive because flyto-core runs on the
worker and the desktop, never on the robot — the loopback address meaning "this
robot" on a Pi means "this container" on a worker. A vision step reads because
the job was dispatched to the machine holding the camera and flyto-core is
running there. Same rule, different answer, because the hardware is on this side
of the boundary.

## Integration points

- **flyto-core** — discovery and the `BaseModule` contract (`await execute()`).
- **A vision gateway** — today flyto-cloud's desktop backend at
  `GET /api/spaces/zone-camera/observation`; later the robot's own.
- **flyto-cloud's evidence layer** — reads the step's `evidence` output from the
  job's variables.

## Verification harness

`scripts/verify_real_camera_closed_loop.py` sits outside the package and never
imports `src/`. It exercises the diagram above end to end: it builds and
installs this tree's wheel, then drives `discover_plugins() → register_all() →
vision.observe → gateway → observation` from a child process that cannot see
`src/`. The report it writes under `results/real-camera-closed-loop/` records the
one request, the wheel's digest and its own, and what the run could not prove.
`tests/test_real_camera_closed_loop.py` pins its decisions offline.
