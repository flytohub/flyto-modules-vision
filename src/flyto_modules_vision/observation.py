"""What counts as an observation, checked at the boundary.

The reason this exists is a real failure mode, not a hypothetical. Before this
package, an authored command reached the gateway with a generic ``http.get``,
which will happily report a 404 page, an empty object or a login redirect as a
successful step. The mission then went unsatisfied with nothing anywhere saying
why, because "no evidence arrived" and "evidence arrived and was rejected" look
identical from the far end.

**Structure is checked here; vocabulary is not.** Whether ``zone.overview`` is
a kind this build knows is flyto-cloud's question, and it already names an
unrecognised kind on the task's own timeline where an operator is looking.
Copying that list here would create a second copy to drift, and a step that
silently dropped a kind the cloud would have accepted is worse than one that
passes it along to be named. So this refuses what is malformed and forwards
what is merely unfamiliar.
"""

from __future__ import annotations

import re
from typing import Any

# A gateway that answers with thousands of items is malfunctioning, and a step
# that forwarded them would push that malfunction into the task record. The
# cloud caps what it reads anyway; this is the earlier, louder cap.
MAX_OBSERVATIONS = 32
MAX_SOURCE_IDENTIFIER_LENGTH = 128

_SOURCE_KEYS = frozenset({"provider", "source_id"})
_SAFE_SOURCE_IDENTIFIER = re.compile(
    rf"[A-Za-z0-9][A-Za-z0-9._:-]{{0,{MAX_SOURCE_IDENTIFIER_LENGTH - 1}}}\Z"
)


class ObservationError(ValueError):
    """The gateway answered, but not with observations."""


def _source(raw: Any, *, index: int) -> dict[str, str]:
    if not isinstance(raw, dict):
        raise ObservationError(f"observation {index} source is not an object")
    if set(raw) != _SOURCE_KEYS:
        raise ObservationError(
            f"observation {index} source must contain exactly provider and source_id"
        )

    source: dict[str, str] = {}
    for field in ("provider", "source_id"):
        value = raw[field]
        if not isinstance(value, str) or not _SAFE_SOURCE_IDENTIFIER.fullmatch(value):
            raise ObservationError(
                f"observation {index} source {field} is not a safe bounded ASCII identifier"
            )
        source[field] = value
    return source


def _one(raw: Any, *, index: int) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ObservationError(f"observation {index} is {type(raw).__name__}, not an object")

    kind = raw.get("kind")
    if not isinstance(kind, str) or not kind.strip():
        raise ObservationError(f"observation {index} has no kind")

    # `usable` must be stated. It is tempting to let absent mean usable — a
    # producer reporting a finding without arguing about it looks like a
    # positive claim — and that is exactly the trap, because this is a
    # cross-language boundary and `false` is the zero value in most of them.
    #
    # Go's most copy-pasted struct tag, `json:"usable,omitempty"` on a bool,
    # emits {"kind":"zone.overview"} for Usable: false — verified by running it.
    # Jackson's NON_DEFAULT does the same. So the one field that decides whether
    # a mission counts as proven would silently invert: a plugin saying "I
    # looked and the view was blocked" would be read as usable evidence, with
    # nothing raising anywhere.
    #
    # An absent value is therefore refused rather than guessed. A producer that
    # cannot say whether what it saw was usable has not told us what we asked.
    if "usable" not in raw:
        raise ObservationError(
            f"observation {index} does not say whether it is usable; state it "
            "explicitly, because an omitted boolean is false in most languages"
        )
    usable = raw["usable"]
    if not isinstance(usable, bool):
        raise ObservationError(
            f"observation {index} has a non-boolean usable: {usable!r}"
        )

    item: dict[str, Any] = {"kind": kind.strip(), "usable": usable}
    detail = raw.get("detail")
    if isinstance(detail, str) and detail.strip():
        item["detail"] = detail.strip()[:500]
    zone = raw.get("zone")
    if isinstance(zone, str) and zone.strip():
        item["zone"] = zone.strip()
    if "source" in raw:
        item["source"] = _source(raw["source"], index=index)
    return item


def parse(payload: Any) -> list[dict[str, Any]]:
    """The observations in what the gateway said, or raise saying what it was.

    An empty list is valid and meaningful: the gateway is there, it has no
    camera or none that has looked yet, and the mission stays unsatisfied. That
    is a different fact from an unreachable gateway, and both are worth being
    able to tell apart in a task's timeline.
    """
    if payload is None:
        raise ObservationError("the gateway returned nothing")
    if isinstance(payload, dict):
        # An endpoint may wrap its list rather than return a bare one.
        inner = payload.get("evidence")
        if not isinstance(inner, list):
            raise ObservationError(
                "the gateway returned an object with no evidence list"
            )
        payload = inner
    if not isinstance(payload, list):
        raise ObservationError(
            f"the gateway returned {type(payload).__name__}, not a list of observations"
        )
    if len(payload) > MAX_OBSERVATIONS:
        raise ObservationError(
            f"the gateway returned {len(payload)} observations, more than {MAX_OBSERVATIONS}"
        )
    return [_one(raw, index=index) for index, raw in enumerate(payload)]


def for_zone(observations: list[dict[str, Any]], zone: str) -> list[dict[str, Any]]:
    """Only what was seen in one zone.

    A mission about the loading bay must not be answered by a clear view of the
    corridor. Observations carrying no zone are dropped rather than kept: a
    producer that cannot say where it looked cannot be taken to have looked
    here, and keeping them would make the filter a suggestion.
    """
    wanted = zone.strip()
    if not wanted:
        return list(observations)
    return [item for item in observations if item.get("zone") == wanted]
