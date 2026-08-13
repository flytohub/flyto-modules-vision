# Docs

This package is small enough that its durable documentation lives in the
project-memory files at the repository root:

- `PROJECT.md` — what this is for and what it is not
- `ARCHITECTURE.md` — module boundaries and runtime shape
- `DECISIONS.md` — why it never captures, and why the address is configuration
- `STATE.md` — what has been verified, and against what
- `ROADMAP.md` — `vision.read_code` and `vision.record`, and what they need
- `README.md` — installation and the step's contract

The observation contract includes optional, bounded `provider`/`source_id`
provenance. `README.md` states the exact parser boundary and the continuing Pi
runner limitation.

Evidence that the loop really closed is not prose: `results/` holds the recorded
real runs, and `scripts/verify_real_camera_closed_loop.py` both produces them
against a live loopback gateway and re-checks a recorded one against its own
digest without contacting anything. `README.md` gives the exact commands.

Handoffs are in `handoffs/`, indexed by `handoffs/_registry.md`.
