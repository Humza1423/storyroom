import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "continuation_evaluation", ROOT / "scripts/evaluate_continuation.py"
)
evaluation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluation)


def case():
    return {
        "id": "one",
        "input": "opaque.mp4",
        "sha256": hashlib.sha256(b"video").hexdigest(),
        "query": "Find the opening jacks.",
        "direction": "after",
        "anchor": [0, 60],
        "context": [0, 240],
        "asset_frames": 900,
        "activity": {
            "start_frame": 0,
            "end_frame": 60,
            "intent": "broad_activity",
            "requested_frames": None,
        },
        "expected": {"end_frame_bounds": [75, 86]},
    }


def verdict(start=0, end=80, *, continuity="same_activity", **extra):
    return {
        "decision": "match",
        "continuity": continuity,
        "intervals": [{"start_frame": start, "end_frame": end, **extra}],
    }


def test_fixed_cases_have_rights_and_independent_review_instructions():
    frozen = json.loads(
        (ROOT / "tests/fixtures/continuation-cases-v1.json").read_text()
    )
    assert frozen["frozen_before_live_comparison"]
    assert len(frozen["cases"]) == 4
    for row in frozen["cases"]:
        assert row["source_page"].startswith("https://")
        assert row["author"] and row["license"] and row["license_url"]
        assert len(row["sha256"]) == 64
    assert "actual playback" in frozen["review_method"]


def test_load_refuses_changed_source_before_any_dispatch(tmp_path):
    (tmp_path / "opaque.mp4").write_bytes(b"changed")
    fixture = tmp_path / "frozen.json"
    rows = [{**case(), "id": str(i)} for i in range(4)]
    fixture.write_text(
        json.dumps({"fps": 30, "frozen_before_live_comparison": True, "cases": rows})
    )
    with pytest.raises(ValueError, match="Source hash changed"):
        evaluation.load_cases(fixture, tmp_path)


def test_assess_rejects_later_occurrence_and_wrong_semantic_continuity():
    assert (
        evaluation.assess(case(), verdict(180, 220))["status"]
        == "disconnected_occurrence"
    )
    assert not evaluation.assess(case(), verdict(continuity="different_activity"))[
        "passed"
    ]
    assert evaluation.assess(case(), verdict())["passed"]


@pytest.mark.parametrize(
    "changes", [{"continues_after": True}, {"boundary_conflict_after": True}]
)
def test_unresolved_boundary_cannot_pass(changes):
    result = evaluation.assess(case(), verdict(**changes))
    assert not result["boundary_pass"]
    assert not result["passed"]


def test_provider_failure_not_counted_as_no_match_and_baseline_semantics_not_invented():
    assert (
        evaluation.assess(case(), None, "provider_quota")["status"]
        == "inspection_failed"
    )
    old = verdict()
    old.pop("continuity")
    result = evaluation.assess(case(), old)
    assert result["boundary_pass"]
    assert result["semantic_continuity"] == "not_separately_tested"
    assert result["passed"] is None


def test_paired_runner_reserves_before_sdk_and_shares_hard_cap(tmp_path):
    output = tmp_path / "report.json"
    report = {"comparisons": []}
    budget = evaluation.EvaluationBudget(output, report, 1, 240)
    counts = []

    def generate(**kwargs):
        counts.append(
            json.loads(output.read_text())["evaluation_budget"]["generation_attempts"]
        )

    sdk = SimpleNamespace(
        models=SimpleNamespace(
            generate_content=generate, embed_content=lambda **kw: None
        ),
        close=lambda: None,
    )
    ai = SimpleNamespace(embedding_client=lambda: sdk)

    def inspect(query, specs, diagnostics):
        data = grounding.verification_clip(None, 0, 240)
        ai.embedding_client().models.generate_content(
            contents=[
                SimpleNamespace(
                    inline_data=SimpleNamespace(mime_type="video/mp4", data=data)
                )
            ]
        )
        return {"c0": verdict()}, None

    def follow(query, spec, **kwargs):
        return inspect(query, [spec], kwargs["diagnostics"])

    grounding = SimpleNamespace(
        verification_clip=lambda *a: b"video",
        inspect_ranges=inspect,
        inspect_continuation=follow,
    )
    evaluation.run_cases(
        [case()],
        tmp_path,
        output,
        report,
        budget,
        ai,
        SimpleNamespace(FPS=30),
        None,
        grounding,
    )
    assert counts == [1]
    saved = json.loads(output.read_text())
    assert saved["evaluation_budget"]["generation_attempts"] == 1
    assert saved["evaluation_budget"]["supplied_video_seconds"] == 8
    assert saved["comparisons"][0]["status"] == "finished"
    assert saved["comparisons"][1]["status"] == "budget_stopped"
    assert saved["dispatch_counts"]["video_requests"] == 1


def test_resume_preserves_count_and_does_not_repeat_completed_or_interrupted_calls(
    tmp_path,
):
    output = tmp_path / "report.json"
    report = {
        "comparisons": [
            {"case_id": "one", "variant": v, "status": "interrupted"}
            for v in ("general_discovery", "anchored_continuation")
        ],
        "dispatch_counts": {"video_requests": 2, "embedding_requests": 0},
    }
    budget = evaluation.EvaluationBudget(output, report, 8, 240)
    ai = SimpleNamespace(
        embedding_client=lambda: pytest.fail("No completed call may repeat")
    )
    grounding = SimpleNamespace(verification_clip=lambda *a: None)
    evaluation.run_cases(
        [case()],
        tmp_path,
        output,
        report,
        budget,
        ai,
        SimpleNamespace(FPS=30),
        None,
        grounding,
    )
    assert report["dispatch_counts"]["video_requests"] == 2
