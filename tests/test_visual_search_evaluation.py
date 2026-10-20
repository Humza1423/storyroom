"""Metric and answer-key validation tests for the visual-search benchmark."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "evaluate_visual_search.py"
SPEC = importlib.util.spec_from_file_location("evaluate_visual_search", SCRIPT)
evaluation = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(evaluation)


def _dataset():
    videos = [
        {"asset_id": f"asset-{category}-{index}", "category": category}
        for category in range(5)
        for index in range(10)
    ]
    queries = []
    for kind, count in (("positive", 50), ("paraphrase", 25), ("negative", 25)):
        for index in range(count):
            category = index % 5
            row = {
                "id": f"{kind}-{index}",
                "project_id": f"project-{category}",
                "query": f"query {index}",
                "category": str(category),
                "kind": kind,
                "split": "test" if index % 2 else "development",
                "relevant": [],
            }
            if kind != "negative":
                row["relevant"] = [
                    {
                        "asset_id": f"asset-{category}-{index % 10}",
                        "start_sec": 1.0,
                        "end_sec": 2.0,
                    }
                ]
            queries.append(row)
    return {"videos": videos, "queries": queries}


def test_evaluator_counts_relevant_top5_and_measures_boundary_error():
    row = {
        "id": "positive-1",
        "category": "animals",
        "split": "test",
        "kind": "positive",
        "relevant": [{"asset_id": "a", "start_sec": 1, "end_sec": 2}],
    }
    outputs = {
        "positive-1": [
            {"asset_id": "wrong", "start_frame": 30, "end_frame": 60},
            {"asset_id": "a", "start_frame": 32, "end_frame": 61},
        ]
    }

    result = evaluation.evaluate_rows([row], outputs)

    assert result["positive_top5_recall"] == 1
    assert result["positive_top1_accuracy"] == 0
    assert result["top1_precision_on_returned"] == 0
    assert result["median_boundary_error_sec"] == pytest.approx(2 / 30)
    assert result["by_split"]["test"]["queries"] == 1


def test_negative_result_counts_as_false_positive():
    row = {
        "id": "negative-1",
        "category": "animals",
        "split": "test",
        "kind": "negative",
        "relevant": [],
    }

    result = evaluation.evaluate_rows([row], {"negative-1": [{"asset_id": "a"}]})

    assert result["negative_false_positive_rate"] == 1
    assert result["top1_precision_on_returned"] == 0


def test_dataset_requires_the_prespecified_50_25_25_evaluation_shape():
    dataset = evaluation._dataset() if hasattr(evaluation, "_dataset") else _dataset()

    assert evaluation.validate_dataset(dataset) is dataset
    dataset["queries"].pop()
    with pytest.raises(ValueError, match="100 reviewed searches"):
        evaluation.validate_dataset(dataset)


def test_dataset_rejects_answer_key_asset_outside_benchmark():
    dataset = _dataset()
    dataset["queries"][0]["relevant"][0]["asset_id"] = "not-in-dataset"

    with pytest.raises(ValueError, match="outside the benchmark"):
        evaluation.validate_dataset(dataset)


def test_isolated_database_can_live_under_ignored_evaluation_tree(tmp_path):
    repo = tmp_path / "repo"
    benchmark_data = repo / "data" / "evaluation" / "visual-search" / "storyroom-data"
    benchmark_data.mkdir(parents=True)
    (benchmark_data / "storyroom.sqlite").touch()

    assert evaluation.validate_isolated_data_dir(benchmark_data, repo) == benchmark_data


def test_evaluator_refuses_the_normal_database_and_its_parent(tmp_path):
    repo = tmp_path / "repo"
    (repo / "data").mkdir(parents=True)
    (repo / "data" / "storyroom.sqlite").touch()

    with pytest.raises(ValueError, match="normal Storyroom data"):
        evaluation.validate_isolated_data_dir(repo / "data", repo)
    with pytest.raises(ValueError, match="normal Storyroom data"):
        evaluation.validate_isolated_data_dir(repo, repo)


def test_pilot_profile_is_separate_from_full_benchmark():
    videos = [
        {"asset_id": f"a-{category}-{index}", "category": str(category)}
        for category in range(4) for index in range(4)
    ]
    queries = []
    for kind, count in (("positive", 36), ("paraphrase", 12), ("negative", 12)):
        for index in range(count):
            category = index % 4
            queries.append({
                "id": f"{kind}-{index}", "project_id": f"project-{category}",
                "query": f"query {kind} {index}", "category": str(category),
                "kind": kind, "split": "test" if index % 2 else "development",
                "relevant": [] if kind == "negative" else [{
                    "asset_id": f"a-{category}-{index % 4}",
                    "start_sec": 1, "end_sec": 2,
                }],
            })
    pilot = {"videos": videos, "queries": queries}
    assert evaluation.validate_dataset(pilot, "pilot") is pilot
    with pytest.raises(ValueError, match="50 videos"):
        evaluation.validate_dataset(pilot)
    pilot["queries"].pop()
    with pytest.raises(ValueError, match="60 reviewed searches"):
        evaluation.validate_dataset(pilot, "pilot")


def test_broad_result_is_not_counted_as_correct_event():
    row = {
        "id": "q", "category": "sports", "split": "test", "kind": "positive",
        "relevant": [{"asset_id": "a", "start_sec": 1, "end_sec": 2}],
    }
    result = evaluation.evaluate_rows(
        [row], {"q": [{"asset_id": "a", "start_frame": 0, "end_frame": 300}]}
    )
    assert result["positive_asset_top5_recall"] == 1
    assert result["positive_top5_recall"] == 0
    assert result["per_query"][0]["failure_stage"] == "retrieval_miss"


def test_actual_normalized_frame_clock_is_used_when_supplied():
    row = {
        "id": "q", "category": "sports", "split": "test", "kind": "positive",
        "relevant": [{"asset_id": "a", "start_sec": 1, "end_sec": 2}],
    }
    result = evaluation.evaluate_rows(
        [row], {"q": [{"asset_id": "a", "start_frame": 60, "end_frame": 120}]},
        {"a": 60},
    )
    assert result["positive_top5_recall"] == 1
    assert result["median_boundary_error_sec"] == 0


def test_failure_stage_separates_shortlist_verifier_and_boundary():
    row = {
        "kind": "positive", "relevant": [{"asset_id": "a", "start_sec": 1, "end_sec": 2}],
    }
    correct = {"asset_id": "a", "start_frame": 30, "end_frame": 60}
    wrong_range = {"asset_id": "a", "start_frame": 90, "end_frame": 120}
    assert evaluation.classify_miss(row, [], {"ranked_events": []}, {}) == "retrieval_miss"
    assert evaluation.classify_miss(row, [], {
        "ranked_events": [wrong_range],
    }, {}) == "temporal_candidate_miss"
    assert evaluation.classify_miss(row, [], {
        "ranked_events": [correct], "shortlist": [wrong_range],
    }, {}) == "shortlist_miss"
    assert evaluation.classify_miss(row, [], {
        "ranked_events": [correct], "shortlist": [correct],
        "verifier": [{**correct, "accepted": False}],
    }, {}) == "verifier_rejection"
    assert evaluation.classify_miss(row, [], {
        "ranked_events": [correct], "shortlist": [correct],
        "verifier": [{**correct, "accepted": True}],
    }, {}) == "boundary_miss"


def test_cache_only_guard_checks_every_candidate_in_production_batch(tmp_path):
    proxy = tmp_path / "asset" / "proxy.mp4"
    proxy.parent.mkdir()
    provider_calls = []
    batch_calls = []
    cached = {"v:q:hash:0:30": {"decision": "match", "visible_evidence": "movement"}}

    class Provider:
        provider = "gemini"
        model = "embedding"

        def embed_text_query(self, query, job_id=None):
            provider_calls.append(query)
            return [1]

    def batch(query, candidates):
        batch_calls.append(candidates)
        return {}, None

    ai = SimpleNamespace(
        embedding_provider=lambda: Provider(), verify_visual_matches=batch,
        visual_verifier_cache_key=lambda query, proxy_hash, start, end:
            f"v:{query}:{proxy_hash}:{start}:{end}",
    )
    search = SimpleNamespace(rank_distinct_events=lambda *args, **kwargs: [])
    db = SimpleNamespace(cache_get=lambda key: cached.get(key))
    config = SimpleNamespace(EMBED_DIMENSIONS=768)
    traces = {"current": {}}
    evaluation.install_instrumentation(ai, search, db, config, traces, False)
    candidates = [
        ("c1", proxy, "hash", 0, 30),
        ("c2", proxy, "hash", 30, 60),
    ]
    with pytest.raises(RuntimeError, match="refusing a network call"):
        ai.verify_visual_matches("q", candidates)
    assert batch_calls == []
    assert traces["current"]["verifier_cache_hits"] == 1
    assert traces["current"]["verifier_cache_misses"] == 1
    assert traces["current"]["shortlist"][1]["start_frame"] == 30
    with pytest.raises(RuntimeError, match="refusing a network call"):
        ai.embedding_provider().embed_text_query("uncached")
    assert provider_calls == []


def test_batch_trace_preserves_cached_verdict_when_other_candidate_fails(tmp_path):
    proxy = tmp_path / "asset" / "proxy.mp4"
    proxy.parent.mkdir()
    cached_verdict = SimpleNamespace(decision="match", visible_evidence="visible movement")
    batch_error = RuntimeError("provider quota")
    batch_calls = []

    def batch(query, candidates):
        batch_calls.append(candidates)
        return {"c1": cached_verdict}, batch_error

    ai = SimpleNamespace(
        embedding_provider=lambda: SimpleNamespace(provider="gemini", model="embedding"),
        verify_visual_matches=batch,
        visual_verifier_cache_key=lambda query, proxy_hash, start, end:
            f"v:{query}:{proxy_hash}:{start}:{end}",
    )
    search = SimpleNamespace(rank_distinct_events=lambda *args, **kwargs: [])
    db = SimpleNamespace(cache_get=lambda key: cached_verdict if key.endswith(":0:30") else None)
    config = SimpleNamespace(EMBED_DIMENSIONS=768)
    traces = {"current": {}}
    evaluation.install_instrumentation(ai, search, db, config, traces, True)
    verdicts, error = ai.verify_visual_matches("q", [
        ("c1", proxy, "hash", 0, 30), ("c2", proxy, "hash", 30, 60),
    ])

    assert len(batch_calls) == 1
    assert verdicts == {"c1": cached_verdict}
    assert error is batch_error
    assert traces["current"]["verifier_request_attempts"] == 1
    assert traces["current"]["verifier"][0]["accepted"] is True
    assert traces["current"]["verifier"][1]["accepted"] is False
    assert traces["current"]["verifier_error"] == "provider quota"
