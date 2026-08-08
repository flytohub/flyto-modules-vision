# Changelog

## 0.1.0 — unreleased

- First release. One step, `vision.observe`, which reports what a vision
  gateway on the dispatched-to machine can currently see.
- The gateway address is configuration, never a step parameter, so identical
  rooms share one authored workflow and the robot's own camera is a setting
  rather than a rewrite.
- Malformed answers are refused at the boundary; unfamiliar evidence kinds are
  forwarded to be named upstream.
- A refusal still carries an empty `evidence` key, so "the gateway was
  unreachable" does not arrive as the same silence as "nothing was seen".
- `execute` is a coroutine, asserted by a test, and the stand-in base class in
  the suite awaits it exactly as flyto-core does.
- No dependencies. Standard library only.
