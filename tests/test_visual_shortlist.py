"""Focused tests for the opt-in source-diversity shortlist experiment."""

from server.vector_index import distinct_asset_shortlist


def candidate(asset, occurrence):
    return {"id": f"{asset}-{occurrence}", "asset_id": asset}


def test_distinct_sources_get_a_first_pass_before_repeat_events():
    ranked = [
        candidate("a", 1), candidate("a", 2), candidate("a", 3),
        candidate("b", 1), candidate("c", 1), candidate("d", 1),
        candidate("e", 1),
    ]

    shortlist = distinct_asset_shortlist(ranked)

    assert [item["id"] for item in shortlist] == ["a-1", "b-1", "c-1", "d-1", "e-1"]
    assert ranked[1]["id"] == "a-2"  # The original ranking is not changed.


def test_repeated_events_fill_remaining_slots_without_duplicates():
    ranked = [
        candidate("a", 1), candidate("a", 2), candidate("a", 3),
        candidate("b", 1), candidate("b", 2), candidate("c", 1),
    ]

    shortlist = distinct_asset_shortlist(ranked, limit=5)

    assert [item["id"] for item in shortlist] == ["a-1", "b-1", "c-1", "a-2", "b-2"]
    assert len({item["id"] for item in shortlist}) == 5


def test_limits_are_bounded_and_can_allow_more_occurrences_explicitly():
    ranked = [candidate("a", number) for number in range(1, 7)]

    assert distinct_asset_shortlist(ranked, limit=0) == []
    assert distinct_asset_shortlist(ranked, max_per_asset=0) == []
    assert [item["id"] for item in distinct_asset_shortlist(
        ranked, limit=5, max_per_asset=3
    )] == ["a-1", "a-2", "a-3"]
