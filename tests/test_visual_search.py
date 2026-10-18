import json
import subprocess
from types import SimpleNamespace

import pytest
from conftest import create_ready

from server import ai, config, db
from server.models import VisualVerdict
from server.vector_index import (
    ExactVectorIndex,
    collapse_overlapping,
    filter_visual_candidates,
    rank_distinct_events,
)
from server.visual_index import (
    TemporalProfile,
    analyze_frames,
    segment_windows,
    temporal_profile,
)
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
    monkeypatch.setattr(
        ai, "verify_visual_match",
        lambda *_: VisualVerdict(decision="match", visible_evidence="Visible movement"),
    )


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
    assert "score" not in candidate  # cosine rank is not a user confidence
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
    asset = db.one("SELECT frames,visual_proxy_hash FROM assets WHERE id=?", (aid,))
    expected_segments = len(temporal_profile(
        config.asset_dir(aid) / "proxy.mp4", asset["frames"], asset["visual_proxy_hash"]
    ).index_ranges())
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


def test_visual_verifier_uses_clip_and_caches_structured_verdict(client, monkeypatch, clip):
    monkeypatch.setattr(config, "visual_ai_ready", lambda: True)
    from server.media import verification_clip

    video = verification_clip(clip, 0, 24)
    assert video.startswith(b"\x00\x00")

    class FakeVideoClient:
        def __init__(self):
            self.calls = []
            self.models = self

        def generate_content(self, **kwargs):
            self.calls.append(kwargs)
            return SimpleNamespace(
                text='{"decision":"match","visible_evidence":"arms curl the weight"}',
                usage_metadata=SimpleNamespace(
                    prompt_token_count=200,
                    candidates_token_count=15,
                    thoughts_token_count=0,
                ),
            )

        def close(self):
            pass

    fake = FakeVideoClient()
    monkeypatch.setattr(ai, "embedding_client", lambda: fake)
    first = ai.verify_visual_match("Bicep CURLS", clip, "proxy-hash", 0, 24)
    second = ai.verify_visual_match("bicep curls", clip, "proxy-hash", 0, 24)
    assert first == second
    assert first.decision == "match"
    assert len(fake.calls) == 1
    assert fake.calls[0]["model"] == config.VISUAL_VERIFIER_MODEL
    assert fake.calls[0]["config"].response_schema["properties"]["decision"]["enum"] == [
        "match", "no_match", "uncertain"
    ]
    assert db.rows("SELECT status,actual FROM usage") == [
        {"status": "settled", "actual": pytest.approx((200 * config.VISUAL_VERIFIER_INPUT_RATE + 15 * config.VISUAL_VERIFIER_OUTPUT_RATE) / 1e6)}
    ]


def test_visual_verifier_exposes_sanitized_provider_failure(client, monkeypatch, clip, caplog):
    monkeypatch.setattr(config, "visual_ai_ready", lambda: True)

    class FakeProviderFailure(RuntimeError):
        code = 429
        status = "RESOURCE_EXHAUSTED"
        message = (
            "Quota exceeded for verifier; API key=AIza123456789012345678901234 "
            "while reading /Users/hamzah/private/proxy.mp4"
        )
        def __init__(self):
            self.details = {"query": "secret query must not be logged"}

    class FailingVideoClient:
        def __init__(self):
            self.models = self

        def generate_content(self, **_kwargs):
            raise FakeProviderFailure()

        def close(self):
            pass

    monkeypatch.setattr(ai, "embedding_client", FailingVideoClient)
    with (
        caplog.at_level("WARNING", logger="storyroom.ai"),
        pytest.raises(ai.VisualProviderError) as caught,
    ):
        ai.verify_visual_match(
            "secret query must not be logged", clip, "proxy-hash", 0, 24
        )

    message = str(caught.value)
    assert "HTTP 429, RESOURCE_EXHAUSTED" in message
    assert "Quota exceeded for verifier" in message
    assert "API key=[REDACTED]" in message
    assert "[REDACTED_PATH]" in message
    assert caught.value.code == 429
    assert "secret query must not be logged" not in caplog.text
    assert "AIza123456789012345678901234" not in caplog.text
    assert "/Users/hamzah" not in caplog.text
    assert db.rows("SELECT status,actual FROM usage") == [
        {"status": "rejected", "actual": 0}
    ]


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


def test_event_grouping_keeps_repeats_separate_and_never_unions_neighbors():
    profile = TemporalProfile(360, (0, 75, 180, 255, 360), tuple([0.0] * 61))
    rows = [
        {"asset_id": "clip", "asset_name": "opaque.mp4", "start_frame": a, "end_frame": b}
        for a, b in ((0, 60), (30, 90), (75, 135), (180, 240), (245, 305))
    ]
    candidates = rank_distinct_events(
        [(0.8, rows[0]), (0.79, rows[1]), (0.75, rows[2]),
         (0.77, rows[3]), (0.74, rows[4])], {"clip": profile}
    )
    ranges = [(c["start_frame"], c["end_frame"]) for c in candidates]
    assert len(ranges) == 4
    assert ranges[0][0] == 0 and ranges[0][1] <= 75
    assert ranges[1][0] >= 180 and ranges[1][1] <= 255
    assert ranges[2][0] >= 75 and ranges[2][1] <= 180
    assert ranges[3][0] >= 255 and ranges[3][1] <= 360
    assert len({c["id"] for c in candidates}) == 4


def test_visual_search_abstains_on_weak_or_ambiguous_cross_asset_matches():
    candidates = [
        {"id": "jump", "asset_id": "exercise", "score": 0.6669,
         "start_frame": 0, "rank": 1},
        {"id": "swing", "asset_id": "swing", "score": 0.6204,
         "start_frame": 30, "rank": 2},
        {"id": "clean", "asset_id": "clean", "score": 0.6162,
         "start_frame": 90, "rank": 3},
    ]
    result = filter_visual_candidates(candidates)
    assert [item["asset_id"] for item in result] == ["exercise"]
    assert "score" not in result[0]
    assert candidates[0]["score"] == 0.6669  # filtering does not mutate rankings

    # Related exercise prompts can be genuinely ambiguous in this embedding
    # space. Returning one at random is worse than asking for a better prompt.
    ambiguous = [
        {"id": "clean", "asset_id": "clean", "score": 0.684},
        {"id": "swing", "asset_id": "swing", "score": 0.6781},
    ]
    assert filter_visual_candidates(ambiguous) == []

    # A more descriptive clean-and-jerk query separates the correct clip enough
    # to keep it while dropping the visually similar swing clip.
    specific = [
        {"id": "clean", "asset_id": "clean", "score": 0.7017,
         "start_frame": 300, "rank": 1},
        {"id": "swing", "asset_id": "swing", "score": 0.6881,
         "start_frame": 120, "rank": 2},
    ]
    assert [item["asset_id"] for item in filter_visual_candidates(specific)] == ["clean"]

    unsupported = [
        {"id": "exercise", "asset_id": "exercise", "score": 0.6132},
        {"id": "swing", "asset_id": "swing", "score": 0.6033},
    ]
    assert filter_visual_candidates(unsupported) == []


def test_visual_search_keeps_repeated_events_only_when_supported_by_top_score():
    candidates = [
        {"id": "repeat-a", "asset_id": "one-video", "score": 0.715,
         "start_frame": 0, "rank": 1},
        {"id": "repeat-b", "asset_id": "one-video", "score": 0.708,
         "start_frame": 900, "rank": 2},
        {"id": "weak-event", "asset_id": "one-video", "score": 0.653,
         "start_frame": 1800, "rank": 3},
        {"id": "similar-action", "asset_id": "other-video", "score": 0.680,
         "start_frame": 0, "rank": 4},
    ]
    result = filter_visual_candidates(candidates)
    assert [item["id"] for item in result] == ["repeat-a", "repeat-b"]


def test_adaptive_segments_follow_strong_visual_changes_not_fixed_grid():
    import numpy as np

    frames = np.zeros((60, 54, 96), dtype=np.float32)
    frames[13:36, 10:35, 15:35] = 0.8
    frames[36:, 25:48, 48:76] = 0.8
    profile = analyze_frames(frames, 360)
    assert profile.boundaries[0] == 0
    assert profile.boundaries[-1] == 360
    assert all(right - left <= 180 for left, right in profile.events)
    assert any(boundary % 30 != 0 for boundary in profile.boundaries[1:-1])


def test_strong_detail_ranges_narrow_a_mixed_event():
    profile = TemporalProfile(150, (0, 150), tuple([0.0] * 26))
    rows = [
        {"asset_id": "clip", "asset_name": "opaque.mp4", "start_frame": a, "end_frame": b}
        for a, b in ((0, 150), (0, 45), (45, 90), (90, 150))
    ]
    result = rank_distinct_events(
        list(zip((0.7, 0.61, 0.8, 0.79), rows)), {"clip": profile}
    )
    coarse = rank_distinct_events(
        list(zip((0.7, 0.61, 0.8, 0.79), rows)),
        {"clip": profile}, refine_ranges=False,
    )
    assert [(c["start_frame"], c["end_frame"]) for c in coarse] == [(0, 150)]
    assert [(c["start_frame"], c["end_frame"]) for c in result] == [(45, 150)]
