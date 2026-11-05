import hashlib
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "evaluate_activity_search",
    Path(__file__).resolve().parents[1] / "scripts/evaluate_activity_search.py",
)
evaluation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluation)
hit, score = evaluation.hit, evaluation.score


def test_frozen_queries_preserve_the_pre_search_answer_key():
    key = Path(__file__).parent / "fixtures/gemini-fresh-answer-key-v1.json"
    assert hashlib.sha256(key.read_bytes()).hexdigest() == (
        "28d46f70d6c21d56aaa95d469616136f8c2d883c9e05aeb1d1b78f65d4ad10b3"
    )


def test_presence_does_not_allow_unrelated_padding_and_discrete_needs_overlap():
    target = {"asset_id": "a", "start_sec": 2, "end_sec": 4, "label_type": "presence"}
    assert hit({"asset_id": "a", "start_frame": 60, "end_frame": 120}, target)
    assert not hit({"asset_id": "a", "start_frame": 0, "end_frame": 300}, target)
    assert not hit({"asset_id": "b", "start_frame": 60, "end_frame": 120}, target)
    target["label_type"] = "event"
    assert not hit({"asset_id": "a", "start_frame": 100, "end_frame": 130}, target)


def test_negative_and_duration_denominators_are_separate():
    key = {
        "queries": [
            {
                "id": "p",
                "kind": "positive",
                "requested_duration_sec": 20,
                "relevant": [
                    {
                        "asset_id": "a",
                        "start_sec": 0,
                        "end_sec": 30,
                        "label_type": "presence",
                    }
                ],
            },
            {"id": "n", "kind": "negative", "relevant": []},
        ]
    }
    rows = [
        {
            "id": "p",
            "total_seconds": 1,
            "results": [{"asset_id": "a", "start_frame": 0, "end_frame": 600}],
        },
        {
            "id": "n",
            "total_seconds": 1,
            "results": [{"asset_id": "a", "start_frame": 0, "end_frame": 150}],
        },
    ]
    metrics = score(rows, key)
    assert metrics["top5_relevant"] == 1
    assert metrics["positive_queries"] == 1
    assert metrics["negative_false_returns"] == 1
    assert metrics["returned_first_precision"] == {"correct": 1, "returned": 2}
    assert metrics["duration_fulfilled_with_relevant_cut"] == 1
    rows[0]["results"][0]["end_frame"] = 150
    assert score(rows, key)["duration_fulfilled_with_relevant_cut"] == 0
