# State

- **0.1.0, unreleased.** 35 tests pass with no camera and no flyto-core.

- Verified against the real counterparties, not stand-ins:
  - a built wheel installed into a clean venv with real flyto-core 2.27.0 is
    discovered through the entry point, `execute` is a coroutine, and the
    engine's own `await run()` path returns a clean refusal when no gateway is
    listening;
  - against a live flyto-cloud desktop backend with a real USB camera, the step
    returned four usable `zone.overview` observations 1.2 s old.

- The `execute`-must-be-a-coroutine test exists because
  flyto-modules-robotics 0.1.0 shipped plain functions. All 36 of its unit tests
  passed, because its stand-in base class called `.execute()` directly and the
  engine's contract was never in the room. Every step died on a real install.

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
