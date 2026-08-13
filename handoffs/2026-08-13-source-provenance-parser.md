# Source-provenance parser closure

## Implemented

`observation.py` now accepts optional `source` only as an object containing the
exact keys `provider` and `source_id`. Both values must be nonblank bounded safe
ASCII identifiers. Provider names remain open and domain-neutral. The parser
returns a fresh source dictionary, refuses malformed or extended source shapes,
and keeps legacy observations without provenance valid.

The observation output remains a narrow allowlist. Pixel, image, frame, device,
device-id and topic inputs are not forwarded. Focused regressions cover source
preservation, unfamiliar future providers, non-aliasing, malformed/missing/extra
and unsafe/unbounded values, leakage refusal, legacy compatibility and zone
filtering.

## Boundary

Source provenance identifies a gateway-owned logical source; it does not expose
or prove camera identity and grants no capture authority. This package still
does not implement a full executor loop. The Pi runner continues to reject
non-robotics actions such as `vision.observe`.

Repository-owned verification is performed by the governing host after this
bounded implementation round.
