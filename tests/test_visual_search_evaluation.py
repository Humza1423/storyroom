"""Metric and answer-key validation tests for the visual-search benchmark."""

from __future__ import annotations

import importlib.util
from pathlib import Path

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
