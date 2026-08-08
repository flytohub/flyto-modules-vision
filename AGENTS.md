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
  with plain functions and all 36 unit tests passed, because its stand-in base
  class called `.execute()` directly. Every step died on a real install. The
  stand-in here awaits, and a test asserts the signature.
- **Do not declare a capability nothing can perform.** The evidence layer
  matches a gap to a capability; a module that claims one and returns nothing
  makes a mission stall instead of escalating to something that could do it.

## Verification

```bash
PYTHONPATH=src:. python -m pytest tests/ -q
```

35 tests, none needing a camera or `flyto-core`. Any change to the observation
shape, to where the address comes from, or to what is refused needs a test that
would fail without it.

Keep the project-memory scaffold current in the same change: `PROJECT.md`,
`ARCHITECTURE.md`, `STATE.md`, `ROADMAP.md`, `tasks.md`, `DECISIONS.md`,
`CHANGELOG.md`, `docs/README.md`, `handoffs/_registry.md`.
