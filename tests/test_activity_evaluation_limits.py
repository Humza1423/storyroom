import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

spec = importlib.util.spec_from_file_location(
    "activity_evaluation_limits",
    Path(__file__).resolve().parents[1] / "scripts/evaluate_activity_search.py",
)
evaluation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluation)


def budget_at(tmp_path, attempts=40, seconds=1500):
    output = tmp_path / "report.json"
    report = {"queries": []}
    return output, report, evaluation.EvaluationBudget(output, report, attempts, seconds)


def fake_modules(dispatch):
    sdk = SimpleNamespace(
        models=SimpleNamespace(embed_content=lambda **_: "embedding", generate_content=dispatch),
        close=lambda: None,
    )
    ai = SimpleNamespace(embedding_client=lambda: sdk)
    grounding = SimpleNamespace(verification_clip=lambda _proxy, start, end: f"{start}:{end}".encode())
    return ai, grounding


def video_part(video):
    return SimpleNamespace(inline_data=SimpleNamespace(data=video, mime_type="video/mp4"))


def test_defaults_allow_exact_cap_and_block_next_dispatch(tmp_path):
    output, report, budget = budget_at(tmp_path, attempts=2, seconds=16)
    dispatched = []

    def dispatch(**kwargs):
        # The ledger must already be durable when the SDK is entered.
        saved = json.loads(output.read_text())["evaluation_budget"]
        assert saved["generation_attempts"] == len(dispatched) + 1
        dispatched.append(kwargs)

    ai, grounding = fake_modules(dispatch)
    counts = {"embedding_requests": 0, "video_requests": 0}
    original_client, original_clip = ai.embedding_client, grounding.verification_clip
    with evaluation.observe_dispatches(ai, grounding, budget, counts, 30):
        video = grounding.verification_clip(None, 0, 240)
        client = ai.embedding_client()
        assert client.models.embed_content() == "embedding"
        for _ in range(2):
            client.models.generate_content(contents=["query", video_part(video)])
        with pytest.raises(evaluation.EvaluationLimitReached):
            client.models.generate_content(contents=[video_part(video)])
    assert len(dispatched) == 2
    assert counts == {"embedding_requests": 1, "video_requests": 2}
    assert report["evaluation_budget"]["supplied_video_seconds"] == 16
    assert budget.stopped == "max_generation_attempts"
    assert ai.embedding_client is original_client
    assert grounding.verification_clip is original_clip


@pytest.mark.parametrize("limit,expected_calls", [(31, 1), (32, 2)])
def test_batch_video_seconds_and_retry_are_charged_before_sdk(tmp_path, monkeypatch, limit, expected_calls):
    from server import ai as real_ai
    from server import config

    monkeypatch.setattr(config, "VISUAL_TIER", "unpaid")
    monkeypatch.setattr(real_ai.time, "sleep", lambda _: None)
    output, report, budget = budget_at(tmp_path, seconds=limit)
    calls = []

    class CapacityError(Exception):
        code = 503

    def dispatch(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise CapacityError()
        return "success"

    ai, grounding = fake_modules(dispatch)
    counts = {"embedding_requests": 0, "video_requests": 0}
    with evaluation.observe_dispatches(ai, grounding, budget, counts, 30):
        parts = [video_part(grounding.verification_clip(None, 0, 240)),
                 video_part(grounding.verification_clip(None, 240, 480))]
        if expected_calls == 1:
            with pytest.raises(evaluation.EvaluationLimitReached):
                real_ai._generate_with_unpaid_503_retry(ai.embedding_client(), contents=parts)
        else:
            assert real_ai._generate_with_unpaid_503_retry(ai.embedding_client(), contents=parts) == "success"
    assert len(calls) == expected_calls
    assert report["evaluation_budget"]["generation_attempts"] == expected_calls
    assert report["evaluation_budget"]["supplied_video_seconds"] == 16 * expected_calls
    if expected_calls == 1:
        assert json.loads(output.read_text())["evaluation_stop"]["reason"] == "max_video_seconds"
    else:
        assert "evaluation_stop" not in report


def test_failed_sdk_calls_and_resume_cannot_reset_counter(tmp_path):
    output, report, budget = budget_at(tmp_path, attempts=1, seconds=8)
    report["in_progress_query"] = {"id": "p", "results": [{"start_frame": 1}]}
    ai, grounding = fake_modules(lambda **_: (_ for _ in ()).throw(TimeoutError()))
    counts = {"embedding_requests": 0, "video_requests": 0}
    with evaluation.observe_dispatches(ai, grounding, budget, counts, 30):
        video = grounding.verification_clip(None, 0, 240)
        with pytest.raises(TimeoutError):
            ai.embedding_client().models.generate_content(contents=[video_part(video)])
    saved = json.loads(output.read_text())
    resumed = evaluation.EvaluationBudget(output, saved, 1, 8)
    with pytest.raises(evaluation.EvaluationLimitReached):
        resumed.reserve(8)
    assert saved["in_progress_query"]["results"] == [{"start_frame": 1}]
    assert saved["evaluation_budget"]["generation_attempts"] == 1


def test_rejects_changed_limits_and_historical_report_without_writing(tmp_path):
    output, report, budget = budget_at(tmp_path)
    budget.reserve(8)
    original = output.read_bytes()
    with pytest.raises(ValueError, match="limits changed"):
        evaluation.EvaluationBudget(output, report, 41, 1500)
    with pytest.raises(ValueError, match="Historical report"):
        evaluation.EvaluationBudget(output, {"queries": []}, 40, 1500)
    assert output.read_bytes() == original


@pytest.mark.parametrize("attempts,seconds", [(-1, 1500), (40, -1), (40, float("nan")), (40, float("inf"))])
def test_rejects_invalid_limits(tmp_path, attempts, seconds):
    with pytest.raises(ValueError):
        budget_at(tmp_path, attempts, seconds)


def test_unknown_video_refuses_dispatch(tmp_path):
    _, report, budget = budget_at(tmp_path)
    ai, grounding = fake_modules(lambda **_: pytest.fail("Unaccounted video reached SDK"))
    with (
        evaluation.observe_dispatches(ai, grounding, budget, {"video_requests": 0}, 30),
        pytest.raises(ValueError, match="Unaccounted video"),
    ):
        ai.embedding_client().models.generate_content(contents=[video_part(b"unknown")])
    assert report["evaluation_budget"]["generation_attempts"] == 0


def test_stop_retains_partial_result_and_does_not_start_next_query(tmp_path):
    output, report, budget = budget_at(tmp_path, attempts=0)
    counts, requests = {}, []
    ai, grounding = fake_modules(lambda **_: pytest.fail("Cap must prevent SDK entry"))
    hit = {"asset_id": "a", "start_frame": 0, "end_frame": 120}

    class Client:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, url, **kwargs):
            requests.append(url)
            return SimpleNamespace(
                raise_for_status=lambda: None,
                json=lambda: {"results": [hit], "activity_job_id": "job"},
            )

    job = {"status": "queued", "result": json.dumps({"visual_results": [hit]}), "message": ""}

    def work():
        video = grounding.verification_clip(None, 0, 240)
        try:
            ai.embedding_client().models.generate_content(contents=[video_part(video)])
        except evaluation.EvaluationLimitReached:
            job.update(status="failed", message="inspection stopped")
        return True

    key = {"queries": [{"id": ident, "query": ident, "project_id": "p", "kind": "positive", "relevant": []}
                       for ident in ("one", "two")]}
    evaluation.run_queries(
        None, Client, ai, SimpleNamespace(FPS=30), SimpleNamespace(one=lambda *args: job),
        grounding, SimpleNamespace(once=work), output, report, budget, counts, set(), None, key,
    )
    saved = json.loads(output.read_text())
    assert len(requests) == 1
    assert saved["queries"][0]["results"] == [hit]
    assert saved["queries"][0]["evaluation_stopped"] == "max_generation_attempts"
    assert saved["evaluation_budget"]["generation_attempts"] == 0
    assert saved["unfinished_query_ids"] == ["one", "two"]
    assert not saved["evaluation_complete"]
    assert "in_progress_query" not in saved
