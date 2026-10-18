"""Deterministic adversarial tests for Storyroom's real visual-search pipeline.

These tests use synthetic vectors and temporary SQLite databases. They never
instantiate a Google client or inspect the user's Storyroom data directory.
The bag-vs-kettlebell case intentionally records the current false positive so
that a later ranking fix must change the expected behavior explicitly.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass

import pytest

from server import ai, config, db
from server import search as visual_search
from server.models import VisualVerdict
from server.visual_index import TemporalProfile


class FakeTextProvider:
    provider = "gemini"
    model = "gemini-embedding-2"

    def __init__(self, vectors):
        self.vectors = vectors
        self.queries = []

    def embed_text_query(self, query, job_id=None):
        self.queries.append(query)
        return self.vectors[query]


@dataclass
class Capture:
    raw: list
    events: list


def unit_vector(*values):
    vector = [0.0] * config.EMBED_DIMENSIONS
    norm = math.sqrt(sum(value * value for value in values))
    for index, value in enumerate(values):
        vector[index] = value / norm
    return vector


def describe(items):
    """Compact, JSON-friendly raw/event/result view for assertion messages."""
    return [
        {
            "asset_id": item["asset_id"],
            "asset_name": item.get("asset_name"),
            "start_frame": item.get("start_frame"),
            "end_frame": item.get("end_frame"),
            "score": item.get("score"),
        }
        for item in items
    ]


@pytest.fixture
def redteam(monkeypatch, tmp_path):
    """A disposable DB plus fake query vectors and observable ranking stages."""
    data_dir = tmp_path / "isolated-storyroom-data"
    monkeypatch.setattr(config, "DATA", data_dir)
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("GOOGLE_API_KEY", "")
    db.init()

    provider = FakeTextProvider({})
    monkeypatch.setattr(ai, "embedding_provider", lambda: provider)
    verdicts = {}

    def fake_verify(query, proxy, _hash, start, end):
        decision = verdicts.get((query, proxy.parent.name, start, end), "match")
        return VisualVerdict(
            decision=decision,
            visible_evidence="Observed requested action" if decision == "match" else "",
        )

    monkeypatch.setattr(ai, "verify_visual_match", fake_verify)
    capture = Capture(raw=[], events=[])

    exact_index = visual_search.ExactVectorIndex

    class CapturingExactIndex(exact_index):
        def search(self, query_vector, rows, limit=20):
            scored = super().search(query_vector, rows, limit)
            capture.raw[:] = [
                {**row, "score": round(score, 6)} for score, row in scored
            ]
            return scored

    rank_events = visual_search.rank_distinct_events

    def capture_events(scored, profiles, limit=5, refine_ranges=True):
        events = rank_events(scored, profiles, limit, refine_ranges=refine_ranges)
        if refine_ranges:
            capture.events[:] = [dict(item) for item in events]
        return events

    monkeypatch.setattr(visual_search, "ExactVectorIndex", CapturingExactIndex)
    monkeypatch.setattr(visual_search, "rank_distinct_events", capture_events)

    proxy_hash = "red-team-proxy-hash"
    profiles = {}

    def fake_sha256(_path):
        return proxy_hash

    def fake_temporal_profile(proxy_path, frame_count, _expected_hash):
        return profiles[proxy_path.parent.name]

    monkeypatch.setattr(visual_search, "sha256_file", fake_sha256)
    monkeypatch.setattr(visual_search, "temporal_profile", fake_temporal_profile)

    state = {
        "data_dir": data_dir,
        "provider": provider,
        "capture": capture,
        "proxy_hash": proxy_hash,
        "profiles": profiles,
        "verdicts": verdicts,
    }
    return state


def create_project(name="red-team"):
    project_id = db.uid()
    db.execute(
        "INSERT INTO projects(id,name,created) VALUES(?,?,?)",
        (project_id, name, 1.0),
    )
    return project_id


def add_asset(redteam, project_id, name, vectors, *, frames=None):
    """Insert an indexed asset whose event windows exactly match its vectors."""
    asset_id = db.uid()
    frames = frames or len(vectors) * 60
    asset_dir = redteam["data_dir"] / "media" / asset_id
    asset_dir.mkdir(parents=True)
    (asset_dir / "proxy.mp4").write_bytes(b"synthetic proxy; never sent anywhere")
    profile = TemporalProfile(
        frame_count=frames,
        boundaries=tuple(range(0, frames, 60)) + (frames,),
        change_scores=tuple([0.0] * (frames // 6 + 2)),
    )
    assert len(profile.events) == len(vectors)
    redteam["profiles"][asset_id] = profile

    db.execute(
        """INSERT INTO assets(
            id,project_id,name,hash,bytes,duration,frames,width,height,has_audio,
            status,provenance,visual_proxy_hash
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            asset_id,
            project_id,
            name,
            f"asset-hash-{asset_id}",
            1,
            frames / config.FPS,
            frames,
            320,
            180,
            0,
            "ready",
            json.dumps({"cloud_analysis": True}),
            redteam["proxy_hash"],
        ),
    )
    for index, vector in enumerate(vectors):
        start, end = profile.events[index]
        db.execute(
            """INSERT INTO visual_segments(
                id,asset_id,start_frame,end_frame,provider,model,dimensions,
                index_version,proxy_hash,sampled_frames,embedding,created
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                db.uid(),
                asset_id,
                start,
                end,
                "gemini",
                "gemini-embedding-2",
                config.EMBED_DIMENSIONS,
                config.VISUAL_INDEX_VERSION,
                redteam["proxy_hash"],
                1,
                json.dumps(vector),
                1.0,
            ),
        )
    return asset_id


def run_query(redteam, project_id, query):
    redteam["capture"].raw.clear()
    redteam["capture"].events.clear()
    returned = visual_search.search_visual(project_id, query)
    return {
        "raw": describe(redteam["capture"].raw),
        "events": describe(redteam["capture"].events),
        "returned": describe(returned),
    }


def emit_case(name, report, expected_asset_ids, *, known_finding=False):
    actual = {item["asset_id"] for item in report["returned"]}
    passed = actual == set(expected_asset_ids)
    label = "KNOWN FINDING" if known_finding and not passed else (
        "PASS" if passed else "UNEXPECTED FAILURE"
    )
    print(
        json.dumps(
            {
                "case": name,
                "status": label,
                "raw_segment_ranking": report["raw"],
                "ranked_events": report["events"],
                "returned_candidates": report["returned"],
                "expected_asset_ids": sorted(expected_asset_ids),
            },
            sort_keys=True,
        )
    )
    return passed


def test_redteam_bag_query_exposes_kettlebell_false_positive(redteam):
    """A high cosine score cannot rescue a video that visibly lacks a bag."""
    project_id = create_project("bag-hard-negative")
    bag_query = unit_vector(1.0, 0.0)
    kettle_id = add_asset(
        redteam, project_id, "opaque-kettle-a17c.mp4", [unit_vector(0.82, 0.572)]
    )
    boxing_id = add_asset(
        redteam, project_id, "opaque-boxing-b42d.mp4", [unit_vector(0.67, 0.742)]
    )
    redteam["provider"].vectors["bag"] = bag_query
    redteam["verdicts"][("bag", kettle_id, 0, 60)] = "no_match"
    redteam["verdicts"][("bag", boxing_id, 0, 60)] = "no_match"

    report = run_query(redteam, project_id, "bag")

    assert report["raw"][0]["asset_id"] == kettle_id
    assert emit_case("bag-vs-kettlebell", report, set())


def test_redteam_wrong_action_is_not_rescued_by_event_refinement(redteam):
    project_id = create_project("wrong-action")
    wrong_action_id = add_asset(
        redteam,
        project_id,
        "opaque-burpees-88af.mp4",
        [unit_vector(0.81, 0.586)],
    )
    jacks_id = add_asset(
        redteam,
        project_id,
        "opaque-jacks-2c91.mp4",
        [unit_vector(0.64, 0.768)],
    )
    redteam["provider"].vectors["jumping jacks"] = unit_vector(1.0, 0.0)
    redteam["verdicts"][("jumping jacks", wrong_action_id, 0, 60)] = "no_match"
    redteam["verdicts"][("jumping jacks", jacks_id, 0, 60)] = "match"

    report = run_query(redteam, project_id, "jumping jacks")

    assert report["raw"][0]["asset_id"] == wrong_action_id
    assert report["events"][0]["asset_id"] == wrong_action_id
    assert emit_case("wrong-action", report, {jacks_id})


def test_redteam_repeated_occurrences_are_distinct_results(redteam):
    project_id = create_project("repeated-events")
    repeated_id = add_asset(
        redteam,
        project_id,
        "opaque-repeated-action.mp4",
        [unit_vector(0.84, 0.543), unit_vector(0.837, 0.547)],
    )
    redteam["provider"].vectors["jumping jacks"] = unit_vector(1.0, 0.0)

    report = run_query(redteam, project_id, "jumping jacks")

    assert emit_case("repeated-events", report, {repeated_id})
    assert len(report["returned"]) == 2
    assert {item["asset_id"] for item in report["returned"]} == {repeated_id}
    assert report["returned"][0]["end_frame"] <= report["returned"][1]["start_frame"]


def test_redteam_unsupported_query_abstains(redteam):
    project_id = create_project("unsupported-query")
    add_asset(
        redteam,
        project_id,
        "opaque-training-a.mp4",
        [unit_vector(1.0, 0.0)],
    )
    add_asset(
        redteam,
        project_id,
        "opaque-training-b.mp4",
        [unit_vector(0.0, 1.0)],
    )
    redteam["provider"].vectors["a cat sleeping"] = unit_vector(-1.0, 0.0)
    for asset_id in redteam["profiles"]:
        redteam["verdicts"][("a cat sleeping", asset_id, 0, 60)] = "no_match"

    report = run_query(redteam, project_id, "a cat sleeping")

    assert emit_case("unsupported-query", report, set())
    assert report["raw"]
    assert report["returned"] == []


def test_redteam_opaque_rename_does_not_change_visual_ranking(redteam):
    project_id = create_project("opaque-filename")
    target_id = add_asset(
        redteam,
        project_id,
        "jumping_jacks_filename.mp4",
        [unit_vector(0.9, 0.436)],
    )
    other_id = add_asset(
        redteam,
        project_id,
        "other-training.mp4",
        [unit_vector(0.65, 0.76)],
    )
    redteam["provider"].vectors["jumping jacks"] = unit_vector(1.0, 0.0)
    redteam["verdicts"][("jumping jacks", other_id, 0, 60)] = "no_match"

    named = run_query(redteam, project_id, "jumping jacks")
    db.execute(
        "UPDATE assets SET name=? WHERE id=?", ("clip-7f3a91.mp4", target_id)
    )
    opaque = run_query(redteam, project_id, "jumping jacks")

    assert emit_case("opaque-filename", opaque, {target_id})
    assert named["returned"]
    assert [item["asset_id"] for item in named["returned"]] == [target_id]
    assert [item["asset_id"] for item in opaque["returned"]] == [target_id]
    assert [item["start_frame"] for item in named["returned"]] == [
        item["start_frame"] for item in opaque["returned"]
    ]


def test_one_asset_negative_query_returns_no_match(redteam):
    project_id = create_project("one-asset-hard-negative")
    curl_id = add_asset(
        redteam, project_id, "opaque-91f7.mp4", [unit_vector(1.0, 0.0)]
    )
    redteam["provider"].vectors["push-ups"] = unit_vector(1.0, 0.0)
    redteam["verdicts"][("push-ups", curl_id, 0, 60)] = "no_match"

    report = run_query(redteam, project_id, "push-ups")
    assert report["raw"][0]["score"] == 1.0
    assert emit_case("one-asset-push-up-negative", report, set())


def test_uncertain_result_is_hidden_and_verifier_failure_is_explicit(redteam, monkeypatch):
    project_id = create_project("uncertain")
    asset_id = add_asset(redteam, project_id, "opaque.mp4", [unit_vector(1.0, 0.0)])
    redteam["provider"].vectors["push-ups"] = unit_vector(1.0, 0.0)
    redteam["verdicts"][("push-ups", asset_id, 0, 60)] = "uncertain"
    assert run_query(redteam, project_id, "push-ups")["returned"] == []

    def unavailable(*_args):
        raise TimeoutError("provider timed out")

    monkeypatch.setattr(ai, "verify_visual_match", unavailable)
    with pytest.raises(ValueError, match="verification is unavailable"):
        visual_search.search_visual(project_id, "push-ups")


def test_safe_provider_diagnostic_reaches_search_error_without_changing_fail_closed_policy(
    redteam, monkeypatch
):
    project_id = create_project("provider-diagnostic")
    add_asset(redteam, project_id, "opaque.mp4", [unit_vector(1.0, 0.0)])
    redteam["provider"].vectors["bag"] = unit_vector(1.0, 0.0)

    def provider_failure(*_args):
        raise ai.VisualProviderError(
            "Gemini video verifier request failed (HTTP 429, RESOURCE_EXHAUSTED): "
            "Quota exceeded. [REDACTED_KEY]",
            429,
            "RESOURCE_EXHAUSTED",
        )

    monkeypatch.setattr(ai, "verify_visual_match", provider_failure)
    with pytest.raises(ValueError, match="HTTP 429, RESOURCE_EXHAUSTED") as caught:
        visual_search.search_visual(project_id, "bag")
    assert "No unverified results were shown" in str(caught.value)

