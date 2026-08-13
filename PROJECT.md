# flyto-modules-vision

## Purpose

Add the workflow step that answers "what can be seen here right now" to Flyto2,
so a mission can be required to *show* something rather than merely to have run.

## Owned surface

- `vision.observe` — the builder step, registered into flyto-core through the
  `flyto.modules` entry point.
- The observation contract: what a vision gateway must return for a step to
  report it as evidence, including optional bounded source provenance without
  pixel data or device identity.
- The closed-loop record: `scripts/verify_real_camera_closed_loop.py` and the
  runs it writes under `results/real-camera-closed-loop/`, which are how "this
  worked against a real gateway" stays checkable rather than remembered.

## Users

- Workflow authors, who get a step in the builder.
- flyto-cloud's evidence layer, which matches the `vision.observe` capability to
  this module when a mission is short of a kind a camera produces.

## Non-goals

- **Capturing.** This never opens a camera. It reads what a gateway already
  observed. See DECISIONS.md.
- **Decoding pixels.** No image library. Whatever owns the camera measures; this
  reports.
- **Extending the Pi runner.** It still rejects non-robotics actions such as
  `vision.observe`; this package does not claim a full executor loop.
- **Owning the evidence vocabulary.** flyto-cloud decides what kinds exist.
- **Being required.** A Flyto2 install without this package is pure software
  automation and stays coherent.
