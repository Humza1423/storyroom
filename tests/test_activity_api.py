"""Search/worker contracts exercised through the API with fake model output."""

import json

import pytest
from conftest import create_ready
from test_visual_search import (
    FakeEmbeddingProvider,
    enable_visual_ai,
    permit_cloud_analysis,
)

from server import ai, db, grounding
from server.worker import once


def ready_index(client, clip, monkeypatch):
    pid, aid = create_ready(client, clip)
    permit_cloud_analysis(client, aid)
    enable_visual_ai(monkeypatch)
    monkeypatch.setattr(ai, "embedding_provider", FakeEmbeddingProvider)
    client.post(
        f"/api/projects/{pid}/visual-index", json={"asset_ids": [aid]}
    ).raise_for_status()
    assert once()
    return pid, aid


def verdict(end=24, continues=False):
    return {
        "intent": "broad_activity",
        "requested_duration_seconds": None,
        "decision": "match",
        "intervals": [
            {
                "start_frame": 0,
                "end_frame": end,
                "suggested_start_frame": 3,
                "suggested_end_frame": 18,
                "continues_before": False,
                "continues_after": continues,
                "visible_evidence": "Athlete visibly throws punches.",
            }
        ],
    }


def test_grounded_search_is_opt_in_and_old_search_unchanged(client, clip, monkeypatch):
    pid, aid = ready_index(client, clip, monkeypatch)
    calls = []

    def inspect(query, specs, **kwargs):
        calls.append((query, specs))
        return {specs[0][0]: verdict()}, None

    monkeypatch.setattr(grounding, "inspect_ranges", inspect)
    old = client.post(
        f"/api/projects/{pid}/search", json={"mode": "visual", "query": "boxing"}
    )
    assert old.status_code == 200, old.text
    assert not calls
    assert "activity" not in old.json()["results"][0]
    response = client.post(
        f"/api/projects/{pid}/search",
        json={"mode": "visual", "query": "boxing", "grounded": True},
    )
    assert response.status_code == 200, response.text
    found = response.json()["results"][0]
    assert found["asset_id"] == aid
    assert (found["start_frame"], found["end_frame"]) == (3, 18)
    assert found["activity"]["end_frame"] == 24
    assert found["activity"]["complete"]
    assert "score" not in found
    assert len(calls) == 1
    assert client.get(found["media_url"]).status_code == 200
    assert db.rows("SELECT * FROM jobs WHERE kind='activity_inspect'") == []


def test_grounded_search_worker_progress_and_completed_results(
    client, clip, monkeypatch
):
    pid, _aid = ready_index(client, clip, monkeypatch)
    calls = []

    def inspect(query, specs, **kwargs):
        calls.append((specs, kwargs))
        return {
            specs[0][0]: verdict(20, True) if len(calls) == 1 else verdict(30)
        }, None

    monkeypatch.setattr(grounding, "inspect_ranges", inspect)
    response = client.post(
        f"/api/projects/{pid}/search",
        json={"mode": "visual", "query": "boxing", "grounded": True},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    job_id = body["activity_job_id"]
    assert body["incomplete"] is True
    assert body["results"][0]["activity"]["complete"] is False
    assert once()
    job = db.one("SELECT * FROM jobs WHERE id=?", (job_id,))
    assert job["status"] == "done", job
    result = json.loads(job["result"])["visual_results"][0]
    assert result["activity"]["complete"]
    assert result["activity"]["end_frame"] == 30
    assert calls[1][1]["job_id"] == job_id
    # A finished continuation is reused, not enqueued and run again.
    repeated = client.post(
        f"/api/projects/{pid}/search",
        json={"mode": "visual", "query": "boxing", "grounded": True},
    )
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["results"][0]["activity"]["complete"]
    assert len(db.rows("SELECT * FROM jobs WHERE kind='activity_inspect'")) == 1


@pytest.mark.parametrize("failure", [False, True])
def test_grounded_search_abstains_and_distinguishes_provider_failure(
    client, clip, monkeypatch, failure
):
    pid, _aid = ready_index(client, clip, monkeypatch)

    def inspect(query, specs, **kwargs):
        if failure:
            return {}, TimeoutError("provider timeout")
        return {
            specs[0][0]: {
                "intent": "broad_activity",
                "decision": "no_match",
                "requested_duration_seconds": None,
                "intervals": [],
            }
        }, None

    monkeypatch.setattr(grounding, "inspect_ranges", inspect)
    response = client.post(
        f"/api/projects/{pid}/search",
        json={"mode": "visual", "query": "a person swimming", "grounded": True},
    )
    assert response.status_code == 200, response.text
    assert response.json()["results"] == []
    assert response.json()["incomplete"] is failure


def test_grounded_duration_shortfall_is_explicit(client, clip, monkeypatch):
    pid, _aid = ready_index(client, clip, monkeypatch)
    short_activity = verdict()
    short_activity["requested_duration_seconds"] = 20
    monkeypatch.setattr(
        grounding,
        "inspect_ranges",
        lambda query, specs, **kwargs: ({specs[0][0]: short_activity}, None),
    )
    response = client.post(
        f"/api/projects/{pid}/search",
        json={"mode": "visual", "query": "20 seconds of boxing", "grounded": True},
    )
    assert response.status_code == 200, response.text
    found = response.json()["results"][0]
    assert found["activity"]["requested_frames"] == 600
    assert found["activity"]["duration_fulfilled"] is False
    assert (found["start_frame"], found["end_frame"]) == (0, 24)
