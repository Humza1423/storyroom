import json
import subprocess
from types import SimpleNamespace

import pytest
from conftest import create_ready

from server import ai, config, db
from server.vector_index import ExactVectorIndex, collapse_overlapping
from server.visual_index import segment_windows
from server.worker import once


class FakeEmbeddingProvider:
    provider = "gemini"
    model = "gemini-embedding-2"

    def __init__(self, fail_on=None, cancel_job=None, fail_error=RuntimeError):
        self.video_calls = 0
        self.fail_on = fail_on
        self.cancel_job = cancel_job
        self.fail_error = fail_error
        self.query_calls = []

    def embed_video_range(self, content, cache_fingerprint, job_id):
        self.video_calls += 1
        assert content
        if self.cancel_job and self.video_calls == self.cancel_job["after_calls"]:
            db.execute("UPDATE jobs SET cancel=1 WHERE id=?", (job_id,))
        if self.video_calls == self.fail_on:
            raise self.fail_error("simulated provider failure")
        return [1.0] + [0.0] * (config.EMBED_DIMENSIONS - 1)

    def embed_text_query(self, query, job_id=None):
        self.query_calls.append(query)
        return [1.0] + [0.0] * (config.EMBED_DIMENSIONS - 1)


def permit_cloud_analysis(client, aid):
    client.put(
        f"/api/assets/{aid}/provenance",
        json={
            "source": "Rights-checked evaluation fixture",
            "author": "Exercise dataset contributors",
            "license": "CC BY 4.0",
            "cloud_analysis": True,
        },
    ).raise_for_status()


def enable_visual_ai(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-only-not-a-real-key")
    monkeypatch.setattr(config, "VISUAL_TIER", "unpaid")
    monkeypatch.setattr(config, "UNPAID_TERMS_ACKNOWLEDGED", True)
    monkeypatch.setattr(config, "visual_ai_ready", lambda: True)


def test_visual_index_search_storybin_and_existing_export(client, clip, monkeypatch):
    pid, aid = create_ready(client, clip)
    permit_cloud_analysis(client, aid)
    enable_visual_ai(monkeypatch)
    provider = FakeEmbeddingProvider()
    monkeypatch.setattr(ai, "embedding_provider", lambda: provider)

    estimate = client.post(
        f"/api/projects/{pid}/visual-index-estimate", json={"asset_ids": [aid]}
    ).json()
    assert estimate["tier"] == "unpaid"
    assert estimate["estimated_usd"] == 0
    assert estimate["reserved_usd"] > 0
    assert estimate["segment_count"] == estimate["frame_count"] == 1

    request = {"asset_ids": [aid]}
    first = client.post(f"/api/projects/{pid}/visual-index", json=request).json()
    repeated = client.post(f"/api/projects/{pid}/visual-index", json=request).json()
    assert first["job_ids"] == repeated["job_ids"]
    assert once()
    job = db.one("SELECT status,result FROM jobs WHERE id=?", (first["job_ids"][0],))
    assert job["status"] == "done"
    assert json.loads(job["result"])["indexed_segments"] == 1
    assert db.one("SELECT COUNT(*) AS n FROM visual_segments WHERE asset_id=?", (aid,))["n"] == 1
    completed_estimate = client.post(
        f"/api/projects/{pid}/visual-index-estimate", json=request
    ).json()
    assert completed_estimate["segment_count"] == 1
    assert completed_estimate["missing_segment_count"] == 0
    assert completed_estimate["frame_count"] == 0
    assert completed_estimate["reserved_usd"] == 0

    result = client.post(
        f"/api/projects/{pid}/search",
        json={"query": "someone lifting weights", "mode": "visual"},
    )
    assert result.status_code == 200, result.text
    candidate = result.json()[0]
    assert candidate["kind"] == "visual"
    assert candidate["asset_id"] == aid
    assert candidate["start_frame"] == 0
    assert candidate["end_frame"] <= 30
    assert candidate["media_url"] == f"/api/assets/{aid}/proxy"
    assert client.get(candidate["media_url"]).status_code == 200

    board = [
        {
            "id": "visual-section",
            "title": "Training",
            "purpose": "",
            "selections": [
                {
                    "id": "visual-choice",
                    "asset_id": aid,
                    "moment_id": None,
                    "start_frame": candidate["start_frame"],
                    "end_frame": candidate["end_frame"],
                    "note": "",
                }
            ],
        }
    ]
    assert client.put(
        f"/api/projects/{pid}/board", json={"revision": 0, "sections": board}
    ).status_code == 200
    assert client.get(f"/api/projects/{pid}").json()["board"] == board
    export = client.post(
        f"/api/projects/{pid}/jobs/export", json={"query": ""}
    ).json()["job_id"]
    assert once()
    assert db.one("SELECT status FROM jobs WHERE id=?", (export,))["status"] == "done"


def test_visual_index_needs_ready_model_and_per_asset_permission(client, clip, monkeypatch):
    pid, aid = create_ready(client, clip)
    enable_visual_ai(monkeypatch)
    response = client.post(
        f"/api/projects/{pid}/visual-index", json={"asset_ids": [aid]}
    )
    assert response.status_code == 400
    assert "permission" in response.json()["detail"].lower()
    assert not db.rows("SELECT * FROM jobs WHERE kind='visual_index'")


@pytest.mark.parametrize("failure", ["quota", "timeout", "cancel"])
def test_partial_visual_index_survives_failure_or_cancel_and_retry(
    client, tmp_path, monkeypatch, failure
):
    long_clip = tmp_path / "long.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-y",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=320x180:rate=30:duration=8",
            "-c:v",
            "libx264",
            "-threads",
            "2",
            "-pix_fmt",
            "yuv420p",
            str(long_clip),
        ],
        check=True,
    )
    pid, aid = create_ready(client, long_clip)
    permit_cloud_analysis(client, aid)
    enable_visual_ai(monkeypatch)
    if failure == "cancel":
        provider = FakeEmbeddingProvider(cancel_job={"after_calls": 2})
    else:
        error = TimeoutError if failure == "timeout" else RuntimeError
        provider = FakeEmbeddingProvider(fail_on=2, fail_error=error)
    monkeypatch.setattr(ai, "embedding_provider", lambda: provider)

    first_job = client.post(
        f"/api/projects/{pid}/visual-index", json={"asset_ids": [aid]}
    ).json()["job_ids"][0]
    assert once()
    failed = db.one("SELECT status,result FROM jobs WHERE id=?", (first_job,))
    assert failed["status"] == ("cancelled" if failure == "cancel" else "failed")
    assert json.loads(failed["result"])["visual_index"]["completed_segments"] == 1
    assert db.one(
        "SELECT COUNT(*) AS n FROM visual_segments WHERE asset_id=?", (aid,)
    )["n"] == 1

    retry = client.post(f"/api/jobs/{first_job}/retry").json()["job_id"]
    assert once()
    done = db.one("SELECT status,result FROM jobs WHERE id=?", (retry,))
    assert done["status"] == "done"
    expected_segments = len(segment_windows(8 * config.FPS))
    assert json.loads(done["result"])["indexed_segments"] == expected_segments
    assert db.one(
        "SELECT COUNT(*) AS n FROM visual_segments WHERE asset_id=?", (aid,)
    )["n"] == expected_segments
    # The already completed range was skipped when retrying.
    assert provider.video_calls == expected_segments + 1


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("model", "different-model"),
        ("index_version", "visual-v1-6s-3s-1fps"),
    ],
)
def test_search_does_not_mix_provider_models_or_old_indexes(
    client, clip, monkeypatch, column, value
):
    pid, aid = create_ready(client, clip)
    permit_cloud_analysis(client, aid)
    enable_visual_ai(monkeypatch)
    provider = FakeEmbeddingProvider()
    monkeypatch.setattr(ai, "embedding_provider", lambda: provider)
    client.post(
        f"/api/projects/{pid}/visual-index", json={"asset_ids": [aid]}
    ).raise_for_status()
    assert once()
    db.execute(f"UPDATE visual_segments SET {column}=? WHERE asset_id=?", (value, aid))
    response = client.post(
        f"/api/projects/{pid}/search",
        json={"query": "lifting", "mode": "visual"},
    )
    assert response.status_code == 400
    assert "index" in response.json()["detail"].lower()
    assert provider.query_calls == []


def test_visual_ranking_uses_vectors_not_video_filenames():
    rows = [
        {
            "asset_id": "misleading-name",
            "asset_name": "jumping_jacks.mp4",
            "start_frame": 0,
            "end_frame": 60,
            "embedding": [0.0, 1.0],
        },
        {
            "asset_id": "opaque-name",
            "asset_name": "clip_opaque_91f7.mp4",
            "start_frame": 0,
            "end_frame": 60,
            "embedding": [1.0, 0.0],
        },
    ]
    results = ExactVectorIndex().search([1.0, 0.0], rows)
    assert results[0][1]["asset_id"] == "opaque-name"


def test_gemini_embedding2_query_format_and_cache(client, monkeypatch):
    enable_visual_ai(monkeypatch)

    class FakeModelClient:
        def __init__(self):
            self.calls = []
            self.models = self

        def embed_content(self, **kwargs):
            self.calls.append(kwargs)
            return SimpleNamespace(
                embeddings=[SimpleNamespace(values=[1.0] + [0.0] * 767)]
            )

        def close(self):
            pass

    fake = FakeModelClient()
    monkeypatch.setattr(ai, "embedding_client", lambda: fake)
    provider = ai.GeminiEmbeddingProvider()
    first = provider.embed_text_query("find a clean kettlebell swing")
    second = provider.embed_text_query("find a clean kettlebell swing")
    assert first == second
    assert len(fake.calls) == 1
    assert fake.calls[0]["contents"] == (
        "task: search result | query: find a clean kettlebell swing"
    )
    assert fake.calls[0]["config"].output_dimensionality == 768
    usage = db.rows("SELECT * FROM usage")[0]
    # The displayed free-tier estimate is $0, but the ledger keeps the
    # conservative list-price reservation because billing status is unverified.
    assert usage["actual"] is None
    assert usage["status"] == "estimated"
    assert usage["reserved"] > 0


def test_short_visual_windows_cover_clip_with_one_second_stride():
    assert config.VISUAL_WINDOW_FRAMES == 60
    assert config.VISUAL_STRIDE_FRAMES == 30
    assert segment_windows(165) == [
        (0, 60),
        (30, 90),
        (60, 120),
        (90, 150),
        (120, 165),
    ]


def test_overlapping_visual_results_keep_best_window_without_broadening():
    rows = [
        {
            "asset_id": "asset",
            "asset_name": "workout.mp4",
            "start_frame": start,
            "end_frame": end,
        }
        for start, end in ((0, 180), (180, 360), (90, 270))
    ]
    candidates = collapse_overlapping(
        [(0.9, rows[0]), (0.8, rows[1]), (0.7, rows[2])],
    )
    assert len(candidates) == 2
    assert [
        (candidate["start_frame"], candidate["end_frame"])
        for candidate in candidates
    ] == [(0, 180), (180, 360)]
