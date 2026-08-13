# Registration round closed: two rounds that did not land, and one that was accepted

Owner: claude
Branch: main
Date: 2026-08-11

## What changed

Documentation only. No file under `src/`, `tests/`, `scripts/`, `results/` or
any packaging metadata was touched by this reconciliation, and no product
behaviour differs because of it.

- `STATE.md` — all three rounds: the two that were not accepted, and the
  accepted one, with what its acceptance does and does not cover.
- `tasks.md` — the two failed rounds kept as one item, the current acceptance
  added as its own, and the publish and camera-command items left open.
- `CHANGELOG.md` — the same facts under 0.1.0, stated so a reader cannot mistake
  acceptance for a release, tag or publication event.
- `handoffs/_registry.md` — the row for this file, rewritten to name all three
  rounds instead of only the first.
- This file.

## Why

The registration work of 2026-08-11 — `register_all` swallowing only an
unresolvable or API-incompatible flyto-core, real plugin failures reaching the
host, discovery repeating without caching — was recorded in `DECISIONS.md` with
no durable record of how the rounds *ended*. A round that ends only in a
conversation is a round nobody can audit later.

Two of the three endings are the ones most likely to be misremembered, and they
pull against each other. Six green checks and a refused job describe the same
round. An accepted revision and an unreleased package describe the same package.
Both pairs belong in the same record, because writing down only the reassuring
half of either leaves a checkout that reads as further along than it is, and the
next agent would build on a status that never existed.

**Rejected: dropping the failed rounds now that a round has landed.** An
acceptance that erases the two refusals hides which route controls fired and
why, and the first refusal — `cumulative_scope_unbounded` — has no recorded
threshold, so it can fire again the same way. Keeping the history is what makes
the current acceptance legible rather than merely reassuring.

**Rejected: a green-only note.** Recording nothing keeps the checkout consistent
but loses the fact that a control fired. Recording only the green half is worse
than silence, because it is wrong in the direction a reader would act on.

## What the job records say

Stated as received, in the terms the jobs used. Ordered oldest first.

**1. `job_adcfb366a00a409da443a4f7` — not accepted.**

- Six checks green — the six `.flyto/coding.yaml` declares, and the only six it
  declares: `compile`, `lint`, `tests`, `build`, `package-check`,
  `index-verify`.
- Result: `cumulative_scope_unbounded`.
- Change written to this tree: none.
- Accepted: **no**.

**2. `job_711ce173012247dba16dd0ac` — not accepted.**

- Wrote the closure documents for the round above.
- Result: failed validation, for an unplanned diff.
- Accepted: **no**.

**3. `job_d9d5b511348d4ce6978ea0f7` — accepted. This is the current acceptance.**

- Implementation revision, SHA-256:
  `58d6c728f1915a74ed5243c958d387fcc1b695d9d77c1757f88b88df4220eb9a`.
- Its six declared checks — compile, Ruff lint, tests, build, the Twine package
  check and the strict Indexer verify — all passed. These are the same six
  `.flyto/coding.yaml` declares, named by the tool each one runs.
- Accepted: **yes**.

## What the acceptance does not mean

The route accepted that implementation revision after its six declared checks
passed. Nothing follows from that about:

- **Release or tag.** 0.1.0 is unreleased and no tag exists. Acceptance is a
  statement about a revision, not a publication event.
- **PyPI.** The pending publisher is still an owner action in the account
  sidebar, and nothing has been uploaded. `tasks.md` keeps both items open.
- **The Space's camera command.** It still does not point at `vision.observe`.
  That item is open.
- **Camera identity.** No round changes what the closed-loop record already
  states narrowly: a pass proves the configured gateway reported this, through
  flyto-core's public registry, to the installed wheel. It does not prove which
  camera answered, or that one exists. This package holds no device handle it
  could use to check.

## Verified

- The six check names are this repository's own, read from `.flyto/coding.yaml`
  in this checkout, so "six declared checks" names a set that exists here rather
  than an unanchored count.
- The tree is consistent with the documentation-only claim above: this
  reconciliation modified only `STATE.md`, `tasks.md`, `CHANGELOG.md`,
  `handoffs/_registry.md` and this file.

## Not verified

- **The six checks were not re-run from this session.** Every one of them, and
  the indexer MCP verification tool, was refused by an environment permission
  gate here — the same gate the 2026-08-09 handoff recorded, and the same one
  the earlier version of this page recorded. Their passing status is the
  accepted job's measurement, quoted, not an observation this author made. The
  commands are reproducible as written in `AGENTS.md` and `.flyto/coding.yaml`;
  provision the checkers first, because a missing checker and a failing package
  exit alike.
- **The job records themselves were not read.** The three job ids, the
  six-green result, the `cumulative_scope_unbounded` outcome, the failed
  validation, the acceptance and the implementation revision digest were all
  supplied to this session. Nothing in this checkout references those job ids or
  that digest independently, so this page is a faithful transcription and not a
  confirmation. Whoever holds the upstream records should check them against
  this page before relying on it.
- **The revision digest was not recomputed here.** `58d6c728…4220eb9a` is
  recorded as given. Unlike the closed-loop reports under `results/`, there is
  no tool in this checkout that recomputes it from local bytes, so it is a
  reference to an upstream artefact rather than a self-checkable one.
- **Why the first round was refused is still not established.**
  `cumulative_scope_unbounded` names the control that fired; it does not say
  which accumulation crossed which bound, and this checkout carries no threshold
  to check against. The later acceptance shows *a* round can stay inside the
  bound; it does not reveal where the bound is.

## Follow-ups

1. Read the upstream records for all three jobs and, if the first refusal reason
   is specific enough to act on, write down the bound it names — a control that
   fires with no recorded threshold will fire again the same way.
2. Re-run the six declared checks in an environment that permits them, so a
   passing result exists that this repository observed rather than quoted.
3. Keep the open publish and camera-command items honest: an accepted revision
   is not a released one, and none of them move until someone does the work.
