# Changelog

## 0.1.0 — unreleased

- First release. One step, `vision.observe`, which reports what a vision
  gateway on the dispatched-to machine can currently see.
- The gateway address is configuration, never a step parameter, so identical
  rooms share one authored workflow and the robot's own camera is a setting
  rather than a rewrite.
- Malformed answers are refused at the boundary; unfamiliar evidence kinds are
  forwarded to be named upstream.
- Optional `source` provenance is accepted only with exact `provider` and
  `source_id` bounded safe ASCII identifiers. Providers remain an open
  vocabulary, validated source objects are freshly copied, malformed or extra
  fields are refused, and pixel/device/topic data is never forwarded. Existing
  observations without provenance remain valid.
- A refusal still carries an empty `evidence` key, so "the gateway was
  unreachable" does not arrive as the same silence as "nothing was seen".
- `execute` is a coroutine, asserted by a test, and the stand-in base class in
  the suite awaits it exactly as flyto-core does.
- `usable` must be stated explicitly; an omitted value is refused rather than
  read as true. This is a cross-language boundary and `false` is the zero value
  in most languages: Go's `json:"usable,omitempty"` on a bool emits
  `{"kind":"zone.overview"}` for `Usable: false` (verified by running it), and
  Jackson's NON_DEFAULT does the same. Defaulting absent to usable would read a
  plugin saying "I looked and the view was blocked" as usable evidence, on the
  one field that decides whether a mission counts as proven.
- `register_all` swallows only an unresolvable or API-incompatible flyto-core.
  A dependency flyto-core itself cannot import, a module of this package that
  will not load, a refusing decorator and a class that cannot be built now
  reach the host instead of being reported as "flyto-core could not be
  reached". Absence and inner breakage are told apart by where the exception
  was raised, not by its type or its `name`, because a partially initialised
  flyto-core raises errors naming `core.modules.base` exactly as a missing one
  does.
- Registration is repeated on every discovery and never remembered, so a
  registry that was cleared or hot reloaded gets the same module set, the same
  host-assigned ownership and the same capability metadata back.
- No dependencies. Standard library only.
- `scripts/verify_real_camera_closed_loop.py` re-runs the real loop from this
  checkout: it builds and installs this tree's wheel in isolation and drives
  `vision.observe` through flyto-core's public registry against a loopback
  gateway, then writes a report carrying the one request, both digests and the
  boundaries the run did not cross. A read-only mode re-checks a recorded report
  against its own bytes, contacting nothing.
  `tests/test_real_camera_closed_loop.py` pins its refusals offline.
- The registration round is closed with records rather than claims, and the
  records keep the rounds that did not land. `job_adcfb366a00a409da443a4f7` ran
  the six checks `.flyto/coding.yaml` declares and all six were green, but the
  job was not accepted: its result was `cumulative_scope_unbounded` and it wrote
  no change here. `job_711ce173012247dba16dd0ac` wrote that round's closure
  documents and failed validation for an unplanned diff.
- `job_d9d5b511348d4ce6978ea0f7` is the accepted round, implementation revision
  SHA-256
  `58d6c728f1915a74ed5243c958d387fcc1b695d9d77c1757f88b88df4220eb9a`, with its
  six declared checks — compile, Ruff, tests, build, the Twine package check and
  the strict Indexer verify — all passed. Acceptance is the route's statement
  about that revision and nothing more: it confers no release, tag or
  publication status, 0.1.0 remains unreleased, and it says nothing about which
  camera is behind any gateway.
- Two runs are recorded under `results/real-camera-closed-loop/`. The canonical
  one is `20260809T155051Z-042205fa`, SHA-256
  `cb9b117a0189a2ad53330178c8a4f324bd371df9b8fe675214fec8364da1c925`; the first,
  `20260809T124233Z-f9e256cd`, SHA-256
  `453326434b63737a630ed44921d812ac4871ab0ebd94734ab8174a1ef96f9f4f`, stays
  valid and its older report shape is still read.
