# The real-camera closed loop, reproducible from this checkout

Owner: claude
Branch: main
Date: 2026-08-09

## What changed

The first recorded run under `results/real-camera-closed-loop/` named a verifier
and a probe that were not in this repository, so the record could be read but not
reproduced. A record nobody can reproduce ages into a claim. Two files closed
that gap, and a live run has since been made through them:

- `scripts/verify_real_camera_closed_loop.py` (699 lines) — builds this
  checkout's wheel, installs it into a throwaway directory with no dependency
  resolution and no index, and runs `vision.observe` through flyto-core's public
  module registry against a loopback gateway. One in-file child mode does the
  live part; there is no second probe script, so the verifier's own digest
  covers the code that ran.
- `tests/test_real_camera_closed_loop.py` (347 lines) — the verifier's refusals
  and both generations of the report shape, pinned without a camera, a gateway,
  a network or an installed flyto-core.

Nothing under `src/`, no packaging metadata, no existing test and no existing
result was touched.

## Why

**The artefact under test is the wheel, not the working tree.** The child runs
with `PYTHONPATH` replaced by the install target plus flyto-core's `src`, and
with `PYTHONSAFEPATH=1` so the interpreter adds neither the script's directory
nor the current one. A verifier that imported `src/` would prove the author's
files work and say nothing about what a user receives.

**Exactly one HTTP GET, exactly to the contract path.** `urlopen` is wrapped
before the package is imported — `fetch_observations` binds it as a default
argument at definition time, so a later patch would be invisible and the run
would count nothing. A second request, a different URL or a non-GET fails the
run. The gateway base URL is an input; the observation path is not, and the
verifier cross-checks its own copy of the path against the installed package's.

**Only loopback, and nothing that could capture.** Non-loopback hosts,
credentials in the URL, a query, a fragment, a path, and non-`http` schemes are
all refused before anything is built. Inside the child, camera device paths and
capture libraries are refused and recorded, and every socket connection is held
to loopback. The package holds no device handle; these make that observable
rather than merely documented.

**`usable` must be stated.** Every selected item must carry boolean `usable:
true` and must name the requested zone. Absent is refused for the reason the
package refuses it: an omitted boolean is false in most languages on the far
side of this wire. Empty evidence, a module error, a discovery failure and a
wrong zone all fail closed and write nothing.

**Kinds are recorded, never filtered.** Whatever kinds that one real call
returns go into the report. Whether a kind exists is flyto-cloud's question, and
a second copy of that vocabulary here would drift.

**Both report generations are readable.** The first reports written under this
contract state `outcome: passed` rather than a `passed` boolean, and record
`requests_made` as a list of URL strings. The read-only mode accepts that shape
and applies the same rules to it — one GET, to the contract URL, with evidence
that states `usable` — while a report that carries the boolean must still state
it true. A verifier that could not read this repository's own canonical record
would be auditing everything except the thing it exists for.

**Rejected: a helper or probe file.** A second script is a second thing to keep
honest, and its digest would have to be recorded separately to mean anything.
The child mode is a private flag on the one file whose SHA-256 the report
carries.

## Commands

Offline gates, which need no camera, gateway, network or flyto-core:

```bash
python -m compileall -q src tests scripts
python -m ruff check src tests scripts
python -m pytest -o pythonpath=src tests -q
python -m build
python -m twine check dist/flyto_modules_vision-0.1.0-py3-none-any.whl \
    dist/flyto_modules_vision-0.1.0.tar.gz
flyto-index verify . --full-scan --strict --json
```

A real run against a gateway already listening on loopback:

```bash
python scripts/verify_real_camera_closed_loop.py \
    --python /path/to/python \
    --core-src /path/to/flyto-core/src \
    --gateway http://127.0.0.1:9010 \
    --zone arena
```

It writes `results/real-camera-closed-loop/<timestamp>-<token>/report.json` and
prints that path. On any refusal it exits nonzero, writes nothing, and touches
no existing run directory.

Reading the runs this repository has recorded, without contacting anything —
the canonical one first, then the first-generation record:

```bash
python scripts/verify_real_camera_closed_loop.py \
    --check-report results/real-camera-closed-loop/20260809T155051Z-042205fa/report.json \
    --expect-sha256 cb9b117a0189a2ad53330178c8a4f324bd371df9b8fe675214fec8364da1c925

python scripts/verify_real_camera_closed_loop.py \
    --check-report results/real-camera-closed-loop/20260809T124233Z-f9e256cd/report.json \
    --expect-sha256 453326434b63737a630ed44921d812ac4871ab0ebd94734ab8174a1ef96f9f4f
```

That mode reads only: no build, no install, no gateway, nothing written. The
digest is the file's own SHA-256, so a changed byte fails before the schema is
even read.

## Trust boundaries

- A pass proves **the configured gateway reported this, through flyto-core's
  public registry, to the installed wheel**. It does not prove which camera
  answered, or that a camera exists at all. This package deliberately holds no
  device handle it could use to check, so the limit is inherent rather than an
  omission. Every report says so in its own boundary notes.
- The report records the gateway authority, the one request, the wheel's
  SHA-256, the verifier's SHA-256, both git revisions where git can say, and the
  returned evidence. No credential value is read or recorded; the URL is refused
  outright if it carries one.
- `--core-src` names a directory the operator trusts. The verifier does not
  audit flyto-core; it uses it.
- The offline suite exercises the deciding functions directly. It does not build
  a wheel, install one, start a gateway or import flyto-core.

## Verified

- The offline suite, Ruff, and the read-only validation of both recorded reports
  at the digests above passed against this tree. Coverage spans the loopback and
  input refusals, wheel and working-tree isolation, the exactly-one-GET
  invariant, the public registry path, `usable` fail-closed behaviour, zone
  filtering, unfamiliar kinds being forwarded, atomic non-overwriting reports,
  and digest validation of both the current and the first-generation report
  shapes.
- **A live run closed the loop through this verifier**, independently of the
  session that wrote it, and is recorded at
  `results/real-camera-closed-loop/20260809T155051Z-042205fa/report.json`,
  SHA-256
  `cb9b117a0189a2ad53330178c8a4f324bd371df9b8fe675214fec8364da1c925`. It built
  and installed this checkout's wheel in isolation rather than importing the
  working tree, discovered the `vision` plugin and executed `vision.observe`
  through flyto-core's public registry, made exactly one GET to
  `http://127.0.0.1:9010/api/spaces/zone-camera/observation` for zone `arena`,
  and received one `zone.overview` stating `usable` exactly `true`. It recorded
  no camera device access and no pixel decode.
- That run settles what this document previously listed as unproven: the
  registry surface the child reaches for (`clear`, `discover_plugins`,
  `get_plugins`, `get_plugin_modules`, `capabilities`, `execute`) is the surface
  a real flyto-core presented, and `resolve_registry` and `_wants_context`
  resolved against it.
- The first record, `20260809T124233Z-f9e256cd`, SHA-256
  `453326434b63737a630ed44921d812ac4871ab0ebd94734ab8174a1ef96f9f4f`, is
  unchanged and still validates under the read-only mode.

## Not verified

- **A pass is still only about the gateway.** It proves the configured gateway
  reported this, through flyto-core's public registry, to the installed wheel.
  It does not prove the identity of any camera behind that gateway, or that a
  camera exists. The limit is inherent: this package holds no device handle it
  could use to check.
- The live run exercised one flyto-core build, one platform and one gateway
  implementation. Nothing here says the registry surface is stable across other
  builds; the shape is pinned by tests on each side, not compiled together.
- The gates and the read-only checks quoted above were not run from this
  session's shell — `python`, `ruff`, `pytest`, `flyto-index` and the indexer MCP
  tools were all refused by an environment permission gate — so they are the
  harness's measurement rather than commands this author executed. The commands
  are reproducible as written.
- Nothing here says anything about release, tag or publication status.

## Follow-ups

1. Point the Space's camera command at `vision.observe`, and record a run whose
   gateway is the robot's own rather than the desktop's.
2. Re-run the verifier when flyto-core's registry surface changes; it is the
   check that would notice.
