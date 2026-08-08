# State

- **0.1.0, unreleased.** 38 tests pass with no camera and no flyto-core.

- `vision.observe` declares `provides_capability` so a host learns what
  installing this package made available, instead of an operator hand-typing
  the capability into a command. Verified against a built wheel in a clean venv
  with flyto-core: `discover_plugins()` then `capabilities()` returns
  `{'vision.observe': ['vision.observe']}`.

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
