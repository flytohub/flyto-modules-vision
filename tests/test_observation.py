"""What counts as an observation, and what is merely unfamiliar.

The distinction this file exists for: malformed is refused, unrecognised is
forwarded. Whether ``zone.overview`` is a kind the build knows is flyto-cloud's
question and it already names an unknown kind on the task's timeline. A second
copy of that vocabulary here would drift, and a step that silently dropped a
kind the cloud would have accepted is worse than one that passes it on.
"""

from __future__ import annotations

import pytest

from flyto_modules_vision.observation import (
    MAX_OBSERVATIONS,
    MAX_SOURCE_IDENTIFIER_LENGTH,
    ObservationError,
    for_zone,
    parse,
)


def test_a_well_formed_observation_survives():
    out = parse([{"kind": "zone.overview", "usable": True, "detail": "zone-a: view_ok"}])
    assert out == [{"kind": "zone.overview", "usable": True, "detail": "zone-a: view_ok"}]


def test_an_unusable_view_is_kept_not_dropped():
    """A blocked camera is a finding; silence is not."""
    out = parse([{"kind": "zone.overview", "usable": False, "detail": "covered"}])
    assert out[0]["usable"] is False


def test_an_unfamiliar_kind_is_forwarded_to_be_named_upstream():
    out = parse([{"kind": "zone.thermal", "usable": True}])
    assert out[0]["kind"] == "zone.thermal"


def test_source_provenance_is_preserved_for_a_future_provider():
    source = {"provider": "future-provider.v2", "source_id": "gateway:zone-7"}
    out = parse([{"kind": "zone.overview", "usable": True, "source": source}])
    assert out[0]["source"] == source


def test_source_provenance_is_copied_not_aliased():
    source = {"provider": "open-provider", "source_id": "source_1"}
    out = parse([{"kind": "zone.overview", "usable": True, "source": source}])
    assert out[0]["source"] is not source
    source["source_id"] = "changed"
    assert out[0]["source"]["source_id"] == "source_1"


@pytest.mark.parametrize(
    "source",
    [
        None,
        "provider/source",
        {},
        {"provider": "known"},
        {"source_id": "one"},
        {"provider": "known", "source_id": "one", "device_id": "camera-1"},
        {"provider": "", "source_id": "one"},
        {"provider": " known", "source_id": "one"},
        {"provider": "known/provider", "source_id": "one"},
        {"provider": "knøwn", "source_id": "one"},
        {"provider": 7, "source_id": "one"},
    ],
)
def test_malformed_source_provenance_is_refused(source):
    with pytest.raises(ObservationError, match="source"):
        parse([{"kind": "zone.overview", "usable": True, "source": source}])


@pytest.mark.parametrize("field", ["provider", "source_id"])
def test_each_source_identifier_rejects_an_over_limit_value(field):
    source = {"provider": "future-neutral-provider", "source_id": "source-1"}
    source[field] = "x" * (MAX_SOURCE_IDENTIFIER_LENGTH + 1)

    with pytest.raises(ObservationError, match=rf"source {field}"):
        parse([{"kind": "zone.overview", "usable": True, "source": source}])


@pytest.mark.parametrize("extra_key", ["topic", "device", "device_id", "pixels"])
def test_each_forbidden_nested_source_key_is_refused(extra_key):
    source = {
        "provider": "future-neutral-provider",
        "source_id": "source-1",
        extra_key: "not-provenance",
    }

    with pytest.raises(ObservationError, match="exactly provider and source_id"):
        parse([{"kind": "zone.overview", "usable": True, "source": source}])


def test_pixel_device_and_topic_fields_are_not_forwarded():
    out = parse(
        [
            {
                "kind": "zone.overview",
                "usable": True,
                "source": {"provider": "gateway", "source_id": "zone-1"},
                "pixels": "raw",
                "image": "encoded",
                "frame": {"bytes": "raw"},
                "device": "camera",
                "device_id": "camera-1",
                "topic": "camera/front",
            }
        ]
    )
    assert out == [
        {
            "kind": "zone.overview",
            "usable": True,
            "source": {"provider": "gateway", "source_id": "zone-1"},
        }
    ]


def test_legacy_observation_without_source_remains_accepted():
    assert parse([{"kind": "zone.overview", "usable": True}]) == [
        {"kind": "zone.overview", "usable": True}
    ]


def test_an_omitted_usable_is_refused_not_guessed():
    """The cross-language trap, pinned.

    Go's most copy-pasted struct tag -- `json:"usable,omitempty"` on a bool --
    emits {"kind":"zone.overview"} for Usable: false, verified by running it.
    Jackson's NON_DEFAULT does the same. Defaulting absent to True would read a
    plugin saying "I looked and the view was blocked" as usable evidence, on the
    one field that decides whether a mission counts as proven.
    """
    with pytest.raises(ObservationError, match="does not say whether it is usable"):
        parse([{"kind": "zone.overview"}])


def test_a_stated_false_survives():
    """The value the omitting serialiser would have eaten."""
    assert parse([{"kind": "zone.overview", "usable": False}])[0]["usable"] is False


def test_an_empty_list_is_a_real_answer():
    """The gateway is there and has seen nothing. Not the same as unreachable."""
    assert parse([]) == []


def test_a_wrapped_list_is_accepted():
    assert len(parse({"evidence": [{"kind": "zone.overview", "usable": True}]})) == 1


@pytest.mark.parametrize(
    "payload, match",
    [
        (None, "returned nothing"),
        ("<html>404</html>", "not a list"),
        (42, "not a list"),
        ({"status": "ok"}, "no evidence list"),
    ],
)
def test_what_is_not_an_observation_list_is_refused(payload, match):
    with pytest.raises(ObservationError, match=match):
        parse(payload)


@pytest.mark.parametrize(
    "item, match",
    [
        ("zone.overview", "not an object"),
        ({"usable": True}, "no kind"),
        ({"kind": "", "usable": True}, "no kind"),
        ({"kind": "   ", "usable": True}, "no kind"),
        ({"kind": 7, "usable": True}, "no kind"),
        ({"kind": "zone.overview", "usable": "yes"}, "non-boolean usable"),
    ],
)
def test_a_malformed_item_is_refused_with_its_index(item, match):
    with pytest.raises(ObservationError, match=match):
        parse([item])


def test_a_flood_is_refused():
    flood = [{"kind": "zone.overview", "usable": True}] * (MAX_OBSERVATIONS + 1)
    with pytest.raises(ObservationError, match="more than"):
        parse(flood)


def test_detail_is_bounded():
    out = parse([{"kind": "zone.overview", "usable": True, "detail": "x" * 5000}])
    assert len(out[0]["detail"]) == 500


def test_a_zone_filter_keeps_only_that_zone():
    """A mission about the loading bay is not answered by the corridor."""
    items = parse(
        [
            {"kind": "zone.overview", "usable": True, "zone": "bay"},
            {"kind": "zone.overview", "usable": True, "zone": "corridor"},
        ]
    )
    assert [i["zone"] for i in for_zone(items, "bay")] == ["bay"]


def test_zone_filter_preserves_source_provenance():
    source = {"provider": "gateway", "source_id": "bay-1"}
    items = parse(
        [{"kind": "zone.overview", "usable": True, "zone": "bay", "source": source}]
    )
    assert for_zone(items, "bay")[0]["source"] == source


def test_an_observation_with_no_zone_is_dropped_by_a_zone_filter():
    """A producer that cannot say where it looked did not look here."""
    items = parse([{"kind": "zone.overview", "usable": True}])
    assert for_zone(items, "bay") == []


def test_an_empty_filter_keeps_everything():
    items = parse([{"kind": "zone.overview", "usable": True, "zone": "bay"}])
    assert for_zone(items, "  ") == items
