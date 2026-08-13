# flyto-modules-vision

Optional camera-observation modules for [Flyto2](https://flyto2.com) workflows.

A Flyto2 mission can be required to *show* something, not merely to have run.
This package adds the step that answers "what can be seen here right now" — and
nothing else. It never opens a camera.

## Installation

```bash
pip install flyto-modules-vision
```

Installing it is the whole decision. flyto-core discovers the package through
the `flyto.modules` entry point declared in `pyproject.toml`:

```toml
[project.entry-points."flyto.modules"]
vision = "flyto_modules_vision:register_all"
```

`ModuleRegistry.discover_plugins()` calls `register_all()`, which registers
`vision.observe`, and the builder gains the step. Without the package, a mission
that needs to see something has nothing to ask.

`register_all()` imports flyto-core *inside* the function, never at module
scope. A missing or incompatible flyto-core is logged and returned from rather
than raised, because flyto-core loads every plugin in one loop and a raise here
would take discovery down for the others too.

Python 3.11 or newer. There are no runtime dependencies — no image library and
no HTTP client, only the standard library — so the package installs anywhere the
engine does and adds nothing to the desktop build.

## Usage

This package ships one module, `vision.observe`. It asks a vision gateway on the
machine the job was dispatched to what that machine's camera last made out, and
returns it as evidence:

```json
{
  "evidence": [
    {"kind": "zone.overview", "zone": "bay", "usable": true,
     "detail": "bay: view_ok (1.2s ago, mean 141, spread 15)"}
  ],
  "observed": 4, "zone": "bay", "usable": 1
}
```

Declare the step's output as `evidence` and flyto-cloud's evidence layer reads it
from the job's variables, the same path every other output already takes.

| Parameter | Meaning | Default |
|---|---|---|
| `zone` | Report only this zone. A mission about the loading bay must not be answered by a clear view of the corridor. | all zones |

Observations that carry no zone are dropped by a zone filter rather than kept: a
producer that cannot say where it looked cannot be taken to have looked here.

When the gateway cannot be reached, or answers with something that is not
observations, the step returns `evidence: []` alongside `observed: 0`, an `error`
string and the address it tried. `evidence` is present and empty rather than
absent, so "the gateway was unreachable" does not arrive as the same silence as
"this step looked and saw nothing".

## API

The package is importable, and its parsing usable, with no flyto-core present.

| Name | What it is |
|---|---|
| `register_all()` | The entry point flyto-core calls. Imports flyto-core lazily; logs and returns if it is absent. |
| `parse(payload)` | The observations in what the gateway said, or `ObservationError` saying what it was instead. |
| `for_zone(observations, zone)` | Only what was seen in one zone. An empty zone keeps everything. |
| `fetch_observations(*, opener=...)` | The gateway's answer, parsed as JSON but not yet trusted. |
| `gateway_url()` | The configured address, trailing slash stripped. |
| `MODULE_OBSERVE`, `MODULE_IDS`, `CAPABILITIES` | The module ids and the capability each provides, in one table. |
| `capability_for(id)`, `is_vision_step(id)` | Lookups against that table. |
| `OBSERVATION_PATH`, `DEFAULT_GATEWAY_URL`, `GATEWAY_URL_ENV`, `MAX_OBSERVATIONS` | The constants the contract is made of. |
| `GatewayError`, `ObservationError` | "Could not reach it" and "it answered, but not with observations" — different failures, kept distinguishable. |

An observation is an object with a non-empty string `kind` and a boolean
`usable`; `detail` and `zone` are optional strings, and `detail` is truncated.
A bare list is accepted, as is an object wrapping one under `evidence`.

`source` is an optional additive provenance object. When present it must contain
exactly `provider` and `source_id`, both nonblank safe ASCII identifiers bounded
to 128 characters. Provider names are open and domain-neutral, not an enum. A
validated fresh copy is forwarded; malformed source data and unknown source
fields are refused. Pixels, images, frames, device fields and topics are never
forwarded, so provenance identifies a gateway-owned source without turning this
step into a device-identity or image transport boundary. Legacy observations
without `source` remain valid.

**`usable` must be stated.** An absent value is refused, not guessed. This is a
cross-language boundary and `false` is the zero value in most languages: Go's
`json:"usable,omitempty"` drops the field for `false`, so a plugin saying "I
looked and the view was blocked" would arrive as usable evidence, with nothing
raising anywhere. The one field that decides whether a mission counts as proven
does not get a default.

**Structure is refused, vocabulary is forwarded.** A malformed item is rejected
with its index. An unfamiliar `kind` is passed along: whether `zone.overview` is
a kind this build knows is flyto-cloud's question, and it already names an
unrecognised kind on the task's own timeline. A second copy of that list here
would drift. More than `MAX_OBSERVATIONS` items is refused as a malfunctioning
gateway rather than forwarded into the task record.

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

**The observation path is contract, not configuration.** It is the constant
`OBSERVATION_PATH`, and there is no setting for it. An operator who could point
a step at an arbitrary path could point it at anything returning JSON, and the
step would report whatever came back as evidence.

## Architecture

```
flyto-core (engine)
  └─ discover_plugins() → flyto.modules entry point → register_all()
       └─ modules.py: vision.observe
            ├─ gateway.py     where to ask (configuration, never a parameter)
            └─ observation.py what counts as an answer
```

`steps.py` is the one table mapping a module id to the capability it provides.
`gateway` and `observation` know nothing of each other: "could we reach it" and
"did it answer with evidence" are different failures and an operator needs to
tell them apart. Both stay importable with no flyto-core installed, because
flyto-core is imported inside `register_all` and `build_modules` only.

A step runs inside flyto-core, on the machine the job was dispatched to, so the
gateway is genuinely on that machine's loopback. This is the opposite geometry
from flyto-modules-robotics, which declares a plan and hands it to the robot's
own runner because flyto-core never runs on the robot. Same rule — talk to
hardware only from the machine that has it — reaching a different answer because
the hardware is on this side of the boundary.

`execute` is a coroutine. flyto-core runs a module with `return await
self.execute()`; the sibling robotics package shipped plain functions, passed
every unit test against a stand-in that called `.execute()` directly, and died on
every real install. A test asserts the signature here for that reason.

## Development

Read `AGENTS.md`, then `PROJECT.md`, `ARCHITECTURE.md`, `STATE.md` and
`DECISIONS.md` before changing anything. The constraints there are the product,
not style preferences.

The gates are declared in `.flyto/coding.yaml`, which is the file a fresh clone
reads to learn what "verified" means here, and the same commands run in
`.github/workflows/ci.yml` on push and pull request against Python 3.11 and 3.12:

```bash
python -m compileall -q src tests scripts
python -m ruff check src tests scripts
python -m pytest -o pythonpath=src tests -q
python -m build
python -m twine check dist/flyto_modules_vision-0.1.0-py3-none-any.whl dist/flyto_modules_vision-0.1.0.tar.gz
flyto-index verify . --full-scan --strict --json
```

The two distribution artefacts are named rather than globbed, so the check
cannot pass on a stale file left in `dist/` or on a build that produced only one
of them. The strict, full-scan index verification is required after every
implementation round, not only before a release: a gate that runs only at the
end runs after the mistake is expensive.

Any change to the observation shape, to where the address comes from, or to what
is refused needs a test that would fail without it. Keep the project-memory
files current in the same change.

## Testing

```bash
python -m pytest -o pythonpath=src tests -q
```

The suite needs no camera, no gateway, no network and no flyto-core. What it
covers:

- the default address is loopback, the environment overrides it, the path is not
  configurable, and no step parameter can name a host;
- an unreachable gateway, an HTTP error code and an HTML error page each fail as
  a gateway failure rather than as a successful step;
- a well-formed observation survives, a stated `false` survives, an omitted
  `usable` is refused, an unfamiliar kind is forwarded, an empty list is a real
  answer, a wrapped list is accepted, a flood is refused, and `detail` is
  bounded;
- zone filtering keeps only that zone and drops observations that name none;
- the declared modules are the ones registered, `execute` is a coroutine on every
  one of them, the engine's own call path works, each module states a non-blank
  capability, a missing flyto-core is logged rather than raised, and the package
  imports without flyto-core.

The suite also covers the closed-loop verifier described below, and covers it the
same way — offline. Without a camera, a gateway, a network or an installed
flyto-core it pins the loopback and input refusals, wheel-versus-working-tree
isolation, the exactly-one-GET invariant, the public-registry path, `usable`
failing closed, atomic non-overwriting reports, and digest validation of both
recorded report shapes.

No test count is stated anywhere on purpose: a number in prose is wrong the first
time anyone adds a test, and a reader who finds one stale stops trusting the rest
of the document.

## Real closed loop

`scripts/verify_real_camera_closed_loop.py` repeats the real loop from this
checkout. It builds this tree's wheel, installs it into a throwaway directory
with no index and no dependency resolution, and runs `vision.observe` through
flyto-core's public module registry in a child whose `PYTHONPATH` is replaced —
so what is exercised is what a user receives, not `src/`. A passing run makes
exactly one HTTP GET, to the contract path on the configured loopback gateway,
and writes a report into a new timestamped directory only after every check
passes.

It is not one of the gates above, because it needs a vision gateway already
listening on loopback:

```bash
python scripts/verify_real_camera_closed_loop.py \
    --python /path/to/python \
    --core-src /path/to/flyto-core/src \
    --gateway http://127.0.0.1:9010 \
    --zone arena
```

Two runs are recorded. The canonical one is
`results/real-camera-closed-loop/20260809T155051Z-042205fa/report.json`: the
installed wheel, discovered as the `vision` plugin through the entry point, made
one GET to `http://127.0.0.1:9010/api/spaces/zone-camera/observation` for zone
`arena` and received one `zone.overview` stating `usable` exactly `true`, with no
camera device access and no pixel decode recorded. The first run,
`20260809T124233Z-f9e256cd`, remains valid; its older report shape is accepted as
written. Either can be re-checked against its own bytes, contacting nothing:

```bash
python scripts/verify_real_camera_closed_loop.py \
    --check-report results/real-camera-closed-loop/20260809T155051Z-042205fa/report.json \
    --expect-sha256 cb9b117a0189a2ad53330178c8a4f324bd371df9b8fe675214fec8364da1c925

python scripts/verify_real_camera_closed_loop.py \
    --check-report results/real-camera-closed-loop/20260809T124233Z-f9e256cd/report.json \
    --expect-sha256 453326434b63737a630ed44921d812ac4871ab0ebd94734ab8174a1ef96f9f4f
```

A pass proves the configured gateway reported this, through flyto-core's public
registry, to the installed wheel. It does not prove which camera answered, or
that one exists.

## Security

**It does not capture.** It reads what a gateway already observed, so a mission
cannot make a lens fire by asking twice, and a package that cannot capture cannot
be talked into capturing. There is no device handle and no capture call anywhere
in the source.

**It does not decode pixels.** No image library and no image bytes; the
observation is JSON that something else produced.

**It reaches exactly one address, and that address is configuration.** One
request, to a path fixed in the source, with no credential of any kind — the
package neither reads nor stores one, and declares `requires_credentials=False`
and `handles_sensitive_data=False` to the registry. The request times out in
seconds so a wedged gateway fails the step instead of holding the job open, and
the error text a refusal carries is truncated.

**It claims one capability, and only one.** The evidence layer matches a gap to a
capability, so a module that claimed one and returned nothing would make a
mission stall instead of escalating to something that could really do it.

## Limitations

**One module, not three.** `vision.read_code` and `vision.record` are the other
capabilities flyto-cloud's evidence layer names, and neither is shipped:
`read_code` needs a decoder this package has no business shipping, and `record`
needs a camera close enough to the subject to be worth recording. Until something
can perform them, the evidence kinds that need them cannot be satisfied by
anything, anywhere.

**The gateway contract is stated here and implemented in flyto-cloud.** Nothing
compiles the two together; the shape is pinned by tests on each side, so a change
made on one side alone will be found at runtime rather than at build time.

**The entry point is the Python binding of the contribution point.** A plugin
written in another language cannot use `flyto.modules` at all. The
language-neutral manifest that would serve those does not exist yet, and nothing
here should be read as though it does.

**A gateway-derived observation proves what the gateway reported.** It does not
prove the identity of any device behind that gateway, nor that a camera exists.
Every recorded run under `results/real-camera-closed-loop/` says so in its own
boundary notes, and the limit is inherent: this package deliberately holds no
device handle it could use to check.

**This is not a Pi executor loop.** The Pi runner still rejects non-robotics
actions such as `vision.observe`; this package only defines the observation step
for a flyto-core runtime dispatched to the machine that owns the gateway.

**The closed loop is reproducible, but it is not one of the gates.** The
verifier is in this repository and a run can be repeated from this checkout, but
it needs a vision gateway already listening on loopback, which the offline gates
above deliberately do not. A recorded report can be re-checked with no gateway
at all; a new one cannot be produced without one.

## License

Apache-2.0. See `LICENSE` and `NOTICE`.
