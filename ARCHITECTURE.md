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
| `observation` | the shape of an observation | where it came from, HTTP |
| `steps` | module ids and the capability each provides | everything else |
| `modules` | flyto-core's module contract | how to reach a camera |

`gateway` and `observation` are importable and testable with no flyto-core
present. flyto-core is imported inside `register_all` and `build_modules`,
never at module scope.

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
