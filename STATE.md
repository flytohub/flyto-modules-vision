# State

- **0.1.0, unreleased.** The offline suite passes with no camera, no gateway, no
  network and no flyto-core.

- **CI green again on 2026-10-08.** The only CI run on main (2026-08-13) failed
  at lint: Ruff 0.16 widened its default rules and the package declared none.
  `[tool.ruff.lint] select` is now declared and guarded by
  `tests/test_repository_contract.py`. Locally with Ruff 0.16.10 on Python
  3.11: compile, lint, 175 tests, build, Twine check, and
  `flyto-index verify . --full-scan --strict --json` (20/20) passed.

- `vision.observe` declares `provides_capability` so a host learns what
  installing this package made available, instead of an operator hand-typing
  the capability into a command. Verified against a built wheel in a clean venv
  with flyto-core: `discover_plugins()` then `capabilities()` returns
  `{'vision.observe': ['vision.observe']}`.

- Optional observation `source` provenance is additive and closed at the parser
  boundary: exact `provider` and `source_id` safe ASCII identifiers are copied;
  malformed, extra, unsafe or unbounded values are refused. Provider vocabulary
  is open, while pixels, images, frames, device identity and topics are not
  forwarded. Legacy observations remain accepted. This does not add a Pi
  executor path; its runner still rejects non-robotics actions such as
  `vision.observe`.

  This is the **Python** binding of the contribution point. A plugin written in
  another language cannot use the `flyto.modules` entry point at all, and the
  owner's requirement is explicitly that plugins are not language-restricted.
  The language-neutral manifest that would serve those is a separate contract
  and does not exist yet; nothing here should be read as though it does.

- Verified against the real counterparties, not stand-ins:
  - a built wheel installed into a clean venv with real flyto-core 2.27.0 is
    discovered through the entry point, `execute` is a coroutine, and the
    engine's own `await run()` path returns a clean refusal when no gateway is
    listening;
  - against a live flyto-cloud desktop backend with a real USB camera, the step
    returned four usable `zone.overview` observations 1.2 s old.

- **The real closed loop is reproducible from this checkout.**
  `scripts/verify_real_camera_closed_loop.py` builds this tree's wheel, installs
  it into a throwaway directory with no index and no dependency resolution, and
  runs `vision.observe` through flyto-core's public registry in a child whose
  `PYTHONPATH` is replaced, so `src/` is never importable.
  `tests/test_real_camera_closed_loop.py` pins its refusals offline. Neither the
  verifier nor a probe is missing from the repository any more.

  The canonical live run is
  `results/real-camera-closed-loop/20260809T155051Z-042205fa/report.json`,
  SHA-256
  `cb9b117a0189a2ad53330178c8a4f324bd371df9b8fe675214fec8364da1c925`. It
  discovered the `vision` plugin through the entry point, executed
  `vision.observe`, made exactly one GET to
  `http://127.0.0.1:9010/api/spaces/zone-camera/observation` for zone `arena`,
  and received one `zone.overview` stating `usable` exactly `true`. It recorded
  no camera device access and no pixel decode.

  The first recorded run, `20260809T124233Z-f9e256cd`, SHA-256
  `453326434b63737a630ed44921d812ac4871ab0ebd94734ab8174a1ef96f9f4f`, remains
  valid and read-only verifiable by the same tool, which accepts its older
  report shape.

  **What a pass proves.** That the configured gateway reported this, through
  flyto-core's public registry, to the installed wheel. It does not prove the
  identity of any camera behind that gateway, nor that a camera exists: this
  package deliberately holds no device handle it could use to check.

- **The discovery boundary is closed and covered offline.** `register_all`
  swallows only the two flyto-core names it asks for being unresolvable, or
  present without the API; a failure raised from inside an installed flyto-core,
  from this package's own `modules`, from the registration decorator, or from
  building the class travels to the host instead. The suite covers each of
  those, including the case an exception's `name` cannot decide — an error
  raised while flyto-core initialises that names `core.modules.base` itself,
  which is indistinguishable by name from an uninstalled engine.

  It also covers repeated discovery and discovery after `clear()` against a
  stand-in registry modelled on the public surface the closed-loop verifier
  drives on a real engine, asserting the same module set, the same
  host-assigned plugin ownership and the same capability metadata each time.
  Nothing is cached to achieve that, which is what makes the second discovery
  repopulate rather than no-op. All of it runs with no camera, no gateway, no
  network and no flyto-core.

  Not proven here: this is a stand-in registry. The cross-repository smoke
  against the real flyto-core registry and the built wheel is a separate run
  and is not recorded in this checkout.

- **Three rounds are recorded. The first two did not land; the third was
  accepted.** See `handoffs/2026-08-11-registration-closure.md`.

  `job_adcfb366a00a409da443a4f7` ran the six checks `.flyto/coding.yaml`
  declares — `compile`, `lint`, `tests`, `build`, `package-check`,
  `index-verify` — and all six were green. The job was still **not accepted**:
  its result was `cumulative_scope_unbounded`, and it wrote **no change** to
  this tree. Six green checks are a statement about the code the job saw, not a
  statement that the job landed.

  `job_711ce173012247dba16dd0ac` wrote that round's closure documents and
  **failed validation** for an unplanned diff. Written documents are not
  acceptance either.

  `job_d9d5b511348d4ce6978ea0f7` is **accepted**. Implementation revision
  SHA-256
  `58d6c728f1915a74ed5243c958d387fcc1b695d9d77c1757f88b88df4220eb9a`. Its six
  declared checks — compile, Ruff lint, tests, build, the Twine package check
  and the strict Indexer verify — all passed. This is the current acceptance,
  and it supersedes neither of the two failed histories above: all three stay
  recorded, because a checkout that shows only the accepted round hides the
  controls that fired.

  **What the acceptance covers.** The route accepted that implementation
  revision after its six declared checks passed. It is not a release, not a
  tag, not a PyPI publication, and it says nothing about the identity of any
  camera behind any gateway. 0.1.0 is still unreleased and the open publish and
  camera-command items in `tasks.md` are still open.

  Not established: why the route drew the scope boundary where it did on the
  first round. The job records are upstream; this checkout carries the
  outcomes, not the reasoning.

- The `execute`-must-be-a-coroutine test exists because
  flyto-modules-robotics 0.1.0 shipped plain functions. Every one of its unit
  tests passed, because its stand-in base class called `.execute()` directly and
  the engine's contract was never in the room. Every step died on a real
  install.

- **Replaces an interim approach.** Before this package, an authored command
  reached the gateway with a generic `http.get` carrying the URL in operator
  data. That broke the rule the robotics package guards with a test: two rooms
  with identical hardware needed two workflows, and a generic fetch reports a
  404 page as a successful step.

## Risks

- The gateway contract is stated here and implemented in flyto-cloud. Nothing
  compiles both together; the shape is pinned by tests on each side.
- `vision.read_code` and `vision.record` have no producer anywhere, so the
  evidence kinds needing them cannot yet be satisfied by anything.
- **The checks are only as available as the interpreter running them.**
  `.flyto/coding.yaml` and `.github/workflows/ci.yml` declare the same commands
  on purpose, but CI provisions the checkers first (`pip install ruff pytest
  build twine flyto-indexer`) and a local run does not. On a machine where
  `python` resolves to an interpreter carrying only some of them, `python -m
  pytest` and `python -m twine` exit non-zero with `No module named ...` — a
  missing verifier, not a failing package, and the two read identically in a
  route result. Provision the checkers before concluding anything from a red
  run, and never edit the check contract to make one green.
