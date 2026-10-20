"""Explicit visual-result pages never expose unverified or repeated events."""

import json

import pytest

from server import ai, config
from server import search as visual_search
from server.models import VisualVerdict
from server.visual_index import TemporalProfile


def _ranked(count=11):
    return [
        {
            "id": f"visual-{index}",
            "rank": index + 1,
            "kind": "visual",
            "asset_id": "source",
            "asset_name": "opaque-source.mp4",
            "start_frame": index * 60,
            "end_frame": (index + 1) * 60,
            "score": round(1 - index / 100, 4),
        }
        for index in range(count)
    ]


def test_following_pages_use_global_order_not_another_source_cap():
    ranked = _ranked(11)
    # Page zero retains the current first-five selection. After that, the
    # highest remaining events of the same source should not be postponed.
    first, has_more = visual_search._visual_candidate_page(ranked, 0)
    second, second_has_more = visual_search._visual_candidate_page(ranked, 1)
    third, third_has_more = visual_search._visual_candidate_page(ranked, 2)

    assert [item["rank"] for item in first] == [1, 2, 3, 4, 5]
    assert [item["rank"] for item in second] == [6, 7, 8, 9, 10]
    assert [item["rank"] for item in third] == [11]
    assert [has_more, second_has_more, third_has_more] == [True, True, False]
    assert len({item["id"] for item in first + second + third}) == 11


def test_legacy_first_page_diversity_does_not_repeat_events_on_later_pages():
    ranked = _ranked(10)
    for index in range(5, 10):
        ranked[index]["asset_id"] = f"other-{index}"
    first, _ = visual_search._visual_candidate_page(ranked, 0)
    second, _ = visual_search._visual_candidate_page(ranked, 1)
    assert [item["rank"] for item in first] == [1, 2, 6, 7, 8]
    assert [item["rank"] for item in second] == [3, 4, 5, 9, 10]
    assert len({item["id"] for item in first + second}) == 10


def test_eighth_page_is_the_last_requestable_page():
    ranked = _ranked(45)
    eighth, has_more = visual_search._visual_candidate_page(ranked, 7)
    assert [item["rank"] for item in eighth] == [36, 37, 38, 39, 40]
    assert has_more is False
    with pytest.raises(ValueError, match="between 0 and 7"):
        visual_search._visual_candidate_page(ranked, 8)


def test_visual_search_verifies_at_most_one_new_batch_per_explicit_page(
    monkeypatch, tmp_path
):
    proxy_dir = tmp_path / "source"
    proxy_dir.mkdir()
    (proxy_dir / "proxy.mp4").write_bytes(b"test-only fake proxy")
    row = {
        "id": "segment",
        "asset_id": "source",
        "asset_name": "opaque-source.mp4",
        "provenance": json.dumps({"cloud_analysis": True}),
        "frames": 660,
        "visual_proxy_hash": "proxy-hash",
        "index_version": config.VISUAL_INDEX_VERSION,
        "start_frame": 0,
        "end_frame": 60,
        "embedding": json.dumps([1.0, 0.0]),
    }
    profile = TemporalProfile(660, (0, 660), (0.0,) * 112)
    monkeypatch.setattr(visual_search.db, "rows", lambda *_: [dict(row)])
    monkeypatch.setattr(config, "asset_dir", lambda _asset_id: proxy_dir)
    monkeypatch.setattr(visual_search, "sha256_file", lambda _path: "proxy-hash")
    monkeypatch.setattr(visual_search, "temporal_profile", lambda *_: profile)
    monkeypatch.setattr(
        visual_search, "rank_distinct_events", lambda *_args, **_kwargs: _ranked()
    )

    class FakeProvider:
        provider = "gemini"
        model = config.EMBED_MODEL

        def embed_text_query(self, _query):
            return [1.0, 0.0]

    monkeypatch.setattr(ai, "embedding_provider", FakeProvider)
    calls = []

    def verify_batch(_query, candidates):
        calls.append([(item[3], item[4]) for item in candidates])
        return {
            item[0]: VisualVerdict(
                decision="match", visible_evidence="Person visibly performs the action"
            )
            for item in candidates
        }, None

    monkeypatch.setattr(ai, "verify_visual_matches", verify_batch)
    responses = []
    for page in range(3):
        status = {}
        results = visual_search.search_visual(
            "project", "burpees", page=page, status=status
        )
        responses.append((results, status))

    assert len(calls) == 3  # one verification batch per explicit request
    assert list(map(len, calls)) == [5, 5, 1]
    assert [start for batch in calls for start, _ in batch] == [
        index * 60 for index in range(11)
    ]
    assert [item["start_frame"] for results, _ in responses for item in results] == [
        index * 60 for index in range(11)
    ]
    assert [status["page"] for _, status in responses] == [0, 1, 2]
    assert [status["has_more"] for _, status in responses] == [True, True, False]
    assert all("score" not in item for results, _ in responses for item in results)

    with pytest.raises(ValueError, match="No more visual search candidates"):
        visual_search.search_visual("project", "burpees", page=3)
    assert len(calls) == 3  # invalid page made no verifier request


def test_visual_page_request_validation_preserves_other_search_modes(client):
    project_id = client.post(
        "/api/projects", json={"name": "Page validation", "brief": ""}
    ).json()["id"]
    endpoint = f"/api/projects/{project_id}/search"
    for invalid in (-1, 8, "1", 1.5, True):
        response = client.post(
            endpoint, json={"query": "squats", "mode": "visual", "page": invalid}
        )
        assert response.status_code == 422, (invalid, response.text)

    assert client.post(
        endpoint, json={"query": "squats", "mode": "keyword", "page": 1}
    ).status_code == 400
    response = client.post(
        endpoint, json={"query": "squats", "mode": "keyword"}
    )
    assert response.status_code == 200
    assert response.json() == []
