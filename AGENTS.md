# Agent rules

Read `PROJECT.md`, `ARCHITECTURE.md`, `STATE.md` and `DECISIONS.md` before
changing anything here.

This package is one of the reference implementations of the Flyto2 plugin
contract. What it does becomes what the next third-party plugin copies, so the
constraints below are the product, not style preferences.

## Constraints

- **Never open a camera from this package.** No capture, no device handle, no
  image library. A step reads what a gateway already observed. A package that
  cannot capture cannot be talked into capturing.
- **Never put a host in a step parameter.** The gateway address is
  configuration. A test asserts no parameter can name one; do not weaken it.
  This is what makes the robot's own camera a setting rather than a rewrite.
- **The observation path is contract, not configuration.** An operator who can
  set the path can point a step at anything returning JSON, and the step would
  report whatever came back as evidence.
- **No absent-means-true booleans on the wire.** `usable` must be stated. This
  is a cross-language boundary and `false` is the zero value in most languages,
  so an omitted boolean silently inverts the field that decides whether a
  mission counts as proven. Verified: Go's `json:"usable,omitempty"` drops it.
- **Refuse malformed, forward unfamiliar.** Whether a kind exists is
  flyto-cloud's question and it already names unknown kinds on the task's
  timeline. A second copy of that vocabulary here would drift.
- **`flyto-core` is imported inside `register_all` / `build_modules`, never at
  module scope.** `gateway` and `observation` must stay importable and testable
  without it.
- **A missing `flyto-core` is logged, not raised.** Discovery loads every plugin
  in one loop; raising would take down the others.
- **`execute` must be a coroutine.** flyto-core runs a module with
  `return await self.execute()`. The sibling robotics package shipped 0.1.0
  with plain functions and all of its unit tests passed, because its stand-in
  base class called `.execute()` directly. Every step died on a real install.
  The stand-in here awaits, and a test asserts the signature.
- **Do not declare a capability nothing can perform.** The evidence layer
  matches a gap to a capability; a module that claims one and returns nothing
  makes a mission stall instead of escalating to something that could do it.
## Before editing

Query the index before changing code, not after. Both agents share it through
the `flyto-indexer` MCP server, and a post-commit hook keeps it current for
committed work:

- `search` for the symbol or behaviour you are about to change, so you are
  editing the definition rather than one of its callers.
- `impact` on that symbol before a rename, a signature change or a deletion.
  This package is imported by flyto-core through an entry point, so the callers
  that matter are not all in this repository.
- If results look stale, `flyto-index scan .` first. Uncommitted work by the
  other agent is not in the index.

## Verification

Run the repository's own checks — the ones `.flyto/coding.yaml` declares, which
is the file a fresh clone reads to learn what "verified" meant here:

```bash
python -m compileall -q src tests scripts
python -m ruff check src tests scripts
python -m pytest -o pythonpath=src tests -q
python -m build
python -m twine check dist/*
flyto-index verify . --full-scan --strict --json
```

The suite needs no camera, no gateway, no network and no `flyto-core`. Do not
state a test count anywhere: a number in prose is wrong the first time anyone
adds a test, and a reader who finds one stale stops trusting the rest of the
document. State what is covered, not how many times.

The strict, full-scan `flyto-index verify` is required after every
implementation round, not only before a release. It is the gate that catches an
index, a document or an instruction file drifting away from the code, and a gate
that only runs at the end is a gate that runs after the mistake is expensive.

Any change to the observation shape, to where the address comes from, or to what
is refused needs a test that would fail without it.

Keep the project-memory scaffold current in the same change: `PROJECT.md`,
`ARCHITECTURE.md`, `STATE.md`, `ROADMAP.md`, `tasks.md`, `DECISIONS.md`,
`CHANGELOG.md`, `docs/README.md`, `handoffs/_registry.md`.
