"""Activity behavior uses grounded intervals, never filenames or gap merging."""

import copy
import json
from types import SimpleNamespace

import pytest

from server import activities, media


def interval(start=0, end=240, before=False, after=False, cut_start=None, cut_end=None):
    return {
        "start_frame": start,
        "end_frame": end,
        "suggested_start_frame": start if cut_start is None else cut_start,
        "suggested_end_frame": min(start + 150, end) if cut_end is None else cut_end,
        "continues_before": before,
        "continues_after": after,
        "visible_evidence": "The boxer continues throwing punches.",
    }


def result(span=None, intent="broad_activity", query="boxing", asset="asset"):
    verdict = {"intent": intent, "requested_duration_seconds": None}
    return activities._result(
        query, {"asset_id": asset, "rank": 1}, span or interval(), verdict, 0
    )


@pytest.mark.parametrize(
    "query,frames",
    [
        ("20 seconds of boxing", 600),
        ("0.5 minutes of boxing", 900),
        ("2.1 secs of boxing", 63),
        ("boxing", None),
        ("0 seconds boxing", None),
    ],
)
def test_explicit_duration_frames(query, frames):
    assert activities.requested_frames(query) == frames


def test_specific_move_returns_complete_interval_without_padding():
    cut = result(interval(129, 228, cut_start=140, cut_end=210), intent="specific_move")
    assert (cut["start_frame"], cut["end_frame"]) == (129, 228)


def test_broad_cut_honors_coherent_provider_end():
    cut = result(interval(0, 600, cut_start=180, cut_end=290))
    assert (cut["start_frame"], cut["end_frame"]) == (180, 290)


def test_twenty_seconds_overrides_short_recommendation():
    cut = result(
        interval(0, 900, cut_start=30, cut_end=180), query="20 seconds of boxing"
    )
    assert cut["end_frame"] - cut["start_frame"] == 600
    assert cut["activity"]["duration_fulfilled"]


def test_shortfall_does_not_join_separate_actions():
    cuts = [
        result(interval(0, 240), query="20 seconds of boxing"),
        result(interval(600, 840), query="20 seconds of boxing"),
    ]
    kept = activities.distinct_activities(cuts)
    assert len(kept) == 2
    assert all(c["end_frame"] - c["start_frame"] == 240 for c in kept)
    assert all(not c["activity"]["duration_fulfilled"] for c in kept)


def test_grounded_activity_with_a_pause_remains_one_result():
    # The provider established continuity across its internal pause. Local motion
    # changes are not available to this layer and cannot split that evidence.
    cuts = activities.distinct_activities([result(interval(0, 900))])
    assert len(cuts) == 1 and cuts[0]["activity"]["end_frame"] == 900


def test_duplicate_views_suppressed_but_separated_moves_retained():
    cuts = [
        result(interval(0, 240)),
        result(interval(10, 230)),
        result(interval(600, 840)),
        result(interval(0, 240), asset="other"),
    ]
    kept = activities.distinct_activities(cuts)
    assert len(kept) == 3
    assert [c["rank"] for c in kept] == [1, 2, 3]


def test_complete_view_replaces_partial_without_combining_ranges():
    first = result(interval(0, 240, after=True))
    replacement = result(interval(0, 600))
    kept = activities.distinct_activities([first, replacement])
    assert len(kept) == 1
    assert kept[0]["activity"]["end_frame"] == 600
    assert kept[0]["id"] == first["id"]


@pytest.fixture
def worker(monkeypatch):
    state = SimpleNamespace(
        calls=[],
        stored=None,
        rows=[],
        error=None,
        asset={
            "id": "asset",
            "frames": 1800,
            "status": "ready",
            "provenance": json.dumps({"cloud_analysis": True}),
            "visual_proxy_hash": "hash",
        },
        lookups=[],
    )

    def one(sql, params):
        state.lookups.append(params)
        return state.asset

    def execute(sql, params):
        state.stored = json.loads(params[0])

    def inspect(query, specs, **kwargs):
        state.calls.append(specs)
        reply = state.rows.pop(0) if state.rows else interval(120, 420)
        return {
            "c0": {
                "intent": "broad_activity",
                "requested_duration_seconds": None,
                "decision": "match",
                "intervals": [reply],
            }
        }, state.error

    monkeypatch.setattr(activities.db, "one", one)
    monkeypatch.setattr(activities.db, "execute", execute)
    monkeypatch.setattr(activities.media, "sha256_file", lambda path: "hash")
    monkeypatch.setattr(activities.grounding, "inspect_ranges", inspect)
    state.job = {
        "id": "job",
        "project_id": "project",
        "payload": json.dumps(
            {"query": "boxing", "candidates": [result(interval(0, 240, after=True))]}
        ),
        "result": None,
    }
    return state


def test_continuation_uses_30_seconds_and_four_seconds_overlap(worker):
    output = activities.continue_inspection(
        worker.job, lambda: False, lambda *args: None
    )
    spec = worker.calls[0][0]
    assert (spec[6], spec[7]) == (120, 1020)
    assert (spec[3], spec[4]) == (120, 240)
    assert output["visual_results"][0]["activity"]["end_frame"] == 420
    assert output["visual_results"][0]["activity"]["complete"]


def test_disjoint_action_cannot_bridge_gap(worker):
    worker.rows = [interval(600, 840)]
    with pytest.raises(ValueError, match="continuity"):
        activities.continue_inspection(worker.job, lambda: False, lambda *args: None)
    assert worker.stored["visual_results"][0]["activity"]["end_frame"] == 240


def test_cancel_before_request_preserves_partial_result(worker):
    with pytest.raises(media.Cancelled):
        activities.continue_inspection(worker.job, lambda: True, lambda *args: None)
    assert not worker.calls
    assert worker.stored["visual_results"][0]["activity"]["end_frame"] == 240


def test_completed_call_is_persisted_when_cancellation_arrives(worker):
    worker.error = InterruptedError("cancelled")
    with pytest.raises((media.Cancelled, InterruptedError, ValueError)):
        activities.continue_inspection(
            worker.job, lambda: bool(worker.calls), lambda *args: None
        )
    assert worker.stored["visual_results"][0]["activity"]["end_frame"] == 420


def test_quota_failure_keeps_completed_stage_and_retry_resumes(worker):
    worker.rows = [interval(120, 1020, after=True)]
    original = activities.grounding.inspect_ranges

    def quota_on_second(query, specs, **kwargs):
        if len(worker.calls) == 1:
            worker.calls.append(specs)
            return {}, ValueError("quota")
        return original(query, specs, **kwargs)

    from unittest.mock import patch

    with (
        patch.object(activities.grounding, "inspect_ranges", quota_on_second),
        pytest.raises(ValueError),
    ):
        activities.continue_inspection(worker.job, lambda: False, lambda *args: None)
    assert worker.stored["visual_results"][0]["activity"]["end_frame"] == 1020
    resumed = copy.deepcopy(worker.job)
    resumed["result"] = json.dumps(worker.stored)
    worker.rows = [interval(900, 1800)]
    output = activities.continue_inspection(resumed, lambda: False, lambda *args: None)
    assert worker.calls[-1][0][6] == 900
    assert output["visual_results"][0]["activity"]["end_frame"] == 1800


@pytest.mark.parametrize("problem", ["project", "permission", "proxy", "not_ready"])
def test_project_permission_and_proxy_isolation_prevent_calls(worker, problem):
    if problem == "project":
        worker.asset = None
    elif problem == "permission":
        worker.asset["provenance"] = json.dumps({"cloud_analysis": False})
    elif problem == "proxy":
        worker.asset["visual_proxy_hash"] = "changed"
    else:
        worker.asset["status"] = "processing"
    with pytest.raises(ValueError):
        activities.continue_inspection(worker.job, lambda: False, lambda *args: None)
    assert worker.lookups[0] == ("asset", "project")
    assert not worker.calls


def test_inspection_diagnostics_are_bounded_and_survive_resume():
    totals = {"request_attempts": 2, "errors": [{"code": "older"}]}
    for index in range(12):
        activities._merge_diagnostics(
            totals,
            {
                "request_attempts": 1,
                "submitted_video_seconds": 30,
                "error_count": 1,
                "error_code": "timestamp_out_of_context",
                "errors": [{"code": "timestamp_out_of_context"}],
                "candidates": [{"context_start_frame": index * 30}],
            },
        )
        totals = json.loads(json.dumps(totals))  # Existing job result round-trip.
    assert totals["request_attempts"] == 14
    assert totals["submitted_video_seconds"] == 360
    assert totals["error_count"] == 12
    assert len(totals["errors"]) == len(totals["candidates"]) == 5
    assert totals["candidates"][0]["context_start_frame"] == 7 * 30


def test_safe_validation_reason_and_partial_work_are_persisted(worker, monkeypatch):
    class SafeFailure(ValueError):
        safe_message = "Returned times fall outside the supplied video."

    def inspect(*args, diagnostics, **kwargs):
        diagnostics.update(
            error_code="timestamp_out_of_context",
            error_count=1,
            errors=[{"stage": "validation", "code": "timestamp_out_of_context"}],
            candidates=[{"context_start_frame": 120, "context_end_frame": 1020}],
        )
        return {}, SafeFailure("private provider content must not be stored")

    monkeypatch.setattr(activities.grounding, "inspect_ranges", inspect)
    with pytest.raises(ValueError, match="Returned times fall outside"):
        activities.continue_inspection(worker.job, lambda: False, lambda *args: None)
    assert worker.stored["visual_results"][0]["activity"]["end_frame"] == 240
    diagnostics = worker.stored["inspection_diagnostics"]
    assert diagnostics["error_code"] == "timestamp_out_of_context"
    assert diagnostics["error_count"] == 1
    assert "private provider" not in json.dumps(worker.stored)


def test_cancel_records_safe_reason_with_existing_partial_results(worker):
    with pytest.raises(media.Cancelled):
        activities.continue_inspection(worker.job, lambda: True, lambda *args: None)
    assert worker.stored["inspection_diagnostics"]["error_code"] == "cancelled"
    assert worker.stored["visual_results"][0]["activity"]["end_frame"] == 240
