# Roadmap

## Near term

- Publish 0.1.0 to PyPI through Trusted Publishing.
- A worked example of an authored command using `vision.observe`.
- A Pi execution integration, if the runner deliberately gains support beyond
  robotics actions; it currently rejects `vision.observe`.

## Later

- `vision.read_code` — for `device.identifier` and `handover.confirmation`.
  Needs a decoder behind a gateway; this package must still not decode.
- `vision.record` — for `close.image`. Needs a camera close enough to the
  subject to be worth recording, which today means the robot's own.

## Out of scope

- Capturing, encoding or decoding images here. See DECISIONS.md.
- A `url` or `host` step parameter, in any form, for any reason.
- Owning the evidence vocabulary.
