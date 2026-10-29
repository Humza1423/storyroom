"""Activity behavior uses grounded intervals, never filenames or gap merging."""

import copy
import json
from types import SimpleNamespace

import pytest

from server import activities, grounding, media


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


def result(
    span=None, intent="broad_activity", query="boxing", asset="asset", requested=None
):
    verdict = {"intent": intent, "requested_duration_seconds": requested}
    return activities._result(
        query, {"asset_id": asset, "rank": 1}, span or interval(), verdict, 0
    )


@pytest.mark.parametrize(
    "seconds,frames",
    [
        (20, 600),
        (30, 900),
        (2.1, 63),
        (None, None),
    ],
)
def test_edit_duration_maps_to_normalized_frames(seconds, frames):
    assert result(requested=seconds)["activity"]["requested_frames"] == frames


def test_specific_move_returns_complete_interval_without_padding():
    cut = result(interval(129, 228, cut_start=140, cut_end=210), intent="specific_move")
    assert (cut["start_frame"], cut["end_frame"]) == (129, 228)


def test_broad_cut_honors_coherent_provider_end():
    cut = result(interval(0, 600, cut_start=180, cut_end=290))
    assert (cut["start_frame"], cut["end_frame"]) == (180, 290)


def test_twenty_seconds_overrides_short_recommendation():
    cut = result(
        interval(0, 900, cut_start=30, cut_end=180),
        query="20 seconds of boxing",
        requested=20,
    )
    assert cut["end_frame"] - cut["start_frame"] == 600
    assert cut["activity"]["duration_fulfilled"]
    assert cut["activity"]["intent"] == "broad_activity"


def test_provider_edit_duration_is_independent_of_specific_move():
    cut = activities._result(
        "a three-second clip showing a kick",
        {"asset_id": "asset", "rank": 1},
        interval(0, 240),
        {"intent": "specific_move", "requested_duration_seconds": 3},
        0,
    )
    assert cut["activity"]["intent"] == "specific_move"
    assert cut["activity"]["requested_frames"] == 90
    assert cut["end_frame"] - cut["start_frame"] == 90


@pytest.mark.parametrize(
    "query",
    [
        "someone holds a plank for 20 seconds",
        "An athlete completes 20 seconds of a plank before standing",
    ],
)
def test_event_duration_condition_is_not_silently_an_edit_length(query):
    cut = result(interval(0, 900), query=query, intent="specific_move")
    assert cut["activity"]["requested_frames"] is None
    assert cut["end_frame"] - cut["start_frame"] == 900


def test_duration_support_and_boundary_completion_are_independent():
    partial = result(
        interval(120, 960, before=True, after=True),
        query="20 seconds of boxing",
        requested=20,
    )
    assert partial["activity"]["duration_fulfilled"]
    assert not partial["activity"]["complete"]
    short = result(
        interval(120, 360, after=True), query="20 seconds of boxing", requested=20
    )
    assert not short["activity"]["duration_fulfilled"]
    assert not short["activity"]["complete"]
    entire = result(interval(0, 240), query="20 seconds of boxing", requested=20)
    assert entire["activity"]["complete"]
    assert (entire["start_frame"], entire["end_frame"]) == (0, 240)


def test_conflicting_boundary_is_not_a_complete_shortfall():
    span = {**interval(30, 240), "boundary_conflict_after": True}
    cut = result(span, requested=20)
    assert not cut["activity"]["complete"]
    assert not cut["activity"]["duration_fulfilled"]
    assert (cut["start_frame"], cut["end_frame"]) == (30, 240)


def test_shortfall_does_not_join_separate_actions():
    cuts = [
        result(interval(0, 240), query="20 seconds of boxing", requested=20),
        result(interval(600, 840), query="20 seconds of boxing", requested=20),
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
        requests=[],
        outcomes=[],
    )

    def one(sql, params):
        state.lookups.append(params)
        return state.asset

    def execute(sql, params):
        state.stored = json.loads(params[0])

    def inspect(query, spec, **kwargs):
        state.calls.append([spec])
        state.requests.append(copy.deepcopy(kwargs))
        reply = state.rows.pop(0) if state.rows else interval(120, 420)
        verdict = {
            "intent": "broad_activity",
            "requested_duration_seconds": None,
            "decision": "match",
            "intervals": [reply],
            "continuity": "same_activity",
            "continuity_evidence": "The same boxer keeps punching through the overlap.",
        }
        if state.outcomes:
            verdict["boundary_outcome"] = state.outcomes.pop(0)
        return {
            "c0": {
                **verdict,
            }
        }, state.error

    monkeypatch.setattr(activities.db, "one", one)
    monkeypatch.setattr(activities.db, "execute", execute)
    monkeypatch.setattr(activities.media, "sha256_file", lambda path: "hash")
    monkeypatch.setattr(activities.grounding, "inspect_continuation", inspect)
    state.job = {
        "id": "job",
        "project_id": "project",
        "payload": json.dumps(
            {
                "query": "boxing",
                "candidates": [result(interval(0, 240, after=True))],
                "contract_version": grounding.VERSION,
                "continuation_contract_version": grounding.CONTINUATION_VERSION,
            }
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
    assert worker.requests[0]["direction"] == "after"
    assert worker.requests[0]["established_activity"]["start_frame"] == 0
    assert worker.requests[0]["established_activity"]["end_frame"] == 240


def test_continuation_clears_only_the_reinspected_boundary_conflict(worker):
    payload = json.loads(worker.job["payload"])
    payload["candidates"][0]["activity"]["boundary_conflict_after"] = True
    worker.job["payload"] = json.dumps(payload)
    output = activities.continue_inspection(
        worker.job, lambda: False, lambda *args: None
    )
    activity = output["visual_results"][0]["activity"]
    assert activity["complete"]
    assert not activity["boundary_conflict_after"]
    assert activity["end_frame"] == 420


def test_conflicting_reinspection_cannot_invent_progress_or_completion(worker):
    worker.rows = [{**interval(0, 240, after=True), "boundary_conflict_after": True}]
    with pytest.raises(ValueError, match="no progress"):
        activities.continue_inspection(worker.job, lambda: False, lambda *args: None)
    activity = worker.stored["visual_results"][0]["activity"]
    assert activity["end_frame"] == 240
    assert activity["boundary_conflict_after"] and not activity["complete"]


@pytest.mark.parametrize("version", [None, "older-contract"])
def test_old_inspection_job_keeps_partial_results_without_mixing_contracts(
    worker, version
):
    payload = json.loads(worker.job["payload"])
    payload["contract_version"] = version
    worker.job["payload"] = json.dumps(payload)
    with pytest.raises(ValueError, match="run this search again"):
        activities.continue_inspection(worker.job, lambda: False, lambda *args: None)
    assert not worker.calls
    assert worker.stored["visual_results"][0]["activity"]["end_frame"] == 240
    assert worker.stored["inspection_diagnostics"]["error_code"] == "contract_changed"


@pytest.mark.parametrize("version", [None, "older-continuation"])
def test_old_continuation_contract_never_uses_new_rules(worker, version):
    payload = json.loads(worker.job["payload"])
    payload["continuation_contract_version"] = version
    worker.job["payload"] = json.dumps(payload)
    with pytest.raises(ValueError, match="run this search again"):
        activities.continue_inspection(worker.job, lambda: False, lambda *args: None)
    assert not worker.calls
    assert worker.stored["visual_results"][0]["activity"]["end_frame"] == 240


def test_duration_fulfillment_does_not_stop_extent_inspection(worker):
    payload = json.loads(worker.job["payload"])
    payload["query"] = "20 seconds of boxing"
    payload["candidates"] = [result(interval(0, 840, after=True), requested=20)]
    worker.job["payload"] = json.dumps(payload)
    worker.rows = [interval(720, 1620, after=True), interval(1500, 1740)]
    output = activities.continue_inspection(
        worker.job, lambda: False, lambda *args: None
    )
    assert len(worker.calls) == 2
    assert all(
        request["established_activity"]["requested_frames"] == 600
        for request in worker.requests
    )
    activity = output["visual_results"][0]["activity"]
    assert activity["end_frame"] == 1740 and activity["complete"]
    assert (
        output["visual_results"][0]["end_frame"]
        - output["visual_results"][0]["start_frame"]
        == 600
    )


@pytest.mark.parametrize(
    "continuity,evidence",
    [
        ("different_activity", "Another action follows."),
        ("uncertain", "Cannot link them."),
        ("same_activity", ""),
    ],
)
def test_worker_defends_against_overlap_without_semantic_connection(
    worker, monkeypatch, continuity, evidence
):
    def inspect(*args, **kwargs):
        return {
            "c0": {
                "decision": "match",
                "intervals": [interval(120, 420)],
                "continuity": continuity,
                "continuity_evidence": evidence,
            }
        }, None

    monkeypatch.setattr(grounding, "inspect_continuation", inspect)
    with pytest.raises(ValueError, match="visible evidence"):
        activities.continue_inspection(worker.job, lambda: False, lambda *args: None)
    assert worker.stored["visual_results"][0]["activity"]["end_frame"] == 240
    assert not worker.stored["visual_results"][0]["activity"]["complete"]


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
    original = activities.grounding.inspect_continuation

    def quota_on_second(query, specs, **kwargs):
        if len(worker.calls) == 1:
            worker.calls.append([specs])
            return {}, ValueError("quota")
        return original(query, specs, **kwargs)

    from unittest.mock import patch

    with (
        patch.object(activities.grounding, "inspect_continuation", quota_on_second),
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

    monkeypatch.setattr(activities.grounding, "inspect_continuation", inspect)
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


def _premature_stop(worker, intent="broad_activity"):
    worker.asset["frames"] = 900
    payload = json.loads(worker.job["payload"])
    payload["candidates"] = [result(interval(0, 195, after=True), intent=intent)]
    worker.job["payload"] = json.dumps(payload)
    worker.rows = [interval(75, 715), interval(685, 900)]
    worker.outcomes = ["observed_stop", "continues"]


def test_short_recheck_corrects_premature_broad_stop(worker, monkeypatch):
    _premature_stop(worker)
    original = grounding.inspect_continuation

    def inspect(*args, **kwargs):
        if worker.calls:
            retained = worker.stored["visual_results"][0]["activity"]
            assert retained["end_frame"] == 715
            assert not retained["complete"]
        return original(*args, **kwargs)

    monkeypatch.setattr(grounding, "inspect_continuation", inspect)
    output = activities.continue_inspection(
        worker.job, lambda: False, lambda *args: None
    )
    assert len(worker.calls) == 2
    assert worker.calls[0][0][6:] == (75, 900)
    assert worker.calls[1][0][3:5] == (685, 715)
    assert worker.calls[1][0][6:] == (685, 900)
    activity = output["visual_results"][0]["activity"]
    assert activity["end_frame"] == 900 and activity["complete"]
    assert len(output["stop_rechecks"]) == 1


def test_confirmed_short_stop_gets_exactly_one_probe(worker):
    _premature_stop(worker)
    worker.rows[1] = interval(685, 715)
    worker.outcomes[1] = "observed_stop"
    output = activities.continue_inspection(
        worker.job, lambda: False, lambda *args: None
    )
    assert len(worker.calls) == 2
    activity = output["visual_results"][0]["activity"]
    assert activity["end_frame"] == 715 and activity["complete"]
    resumed = {**worker.job, "result": json.dumps(output)}
    activities.continue_inspection(resumed, lambda: False, lambda *args: None)
    assert len(worker.calls) == 2


def test_stop_at_existing_edge_still_gets_one_short_check(worker):
    _premature_stop(worker)
    worker.rows = [
        interval(75, 195),
        interval(165, 405, after=True),
        interval(285, 900),
    ]
    worker.outcomes = ["observed_stop", "continues", "continues"]
    output = activities.continue_inspection(
        worker.job, lambda: False, lambda *args: None
    )
    assert worker.calls[1][0][3:5] == (165, 195)
    assert worker.calls[1][0][6:] == (165, 405)
    assert output["visual_results"][0]["activity"]["complete"]
    assert len(worker.calls) == 3  # Long inspection, one short probe, next long chunk.


def test_new_stop_in_same_direction_cannot_start_a_second_short_probe(worker):
    _premature_stop(worker)
    worker.asset["frames"] = 1800
    worker.rows = [
        interval(75, 715),
        interval(685, 925, after=True),
        interval(805, 1200),
    ]
    worker.outcomes = ["observed_stop", "continues", "observed_stop"]
    with pytest.raises(ValueError, match="one short stop recheck"):
        activities.continue_inspection(worker.job, lambda: False, lambda *args: None)
    assert len(worker.calls) == 3
    activity = worker.stored["visual_results"][0]["activity"]
    assert activity["end_frame"] == 1200 and not activity["complete"]
    assert worker.calls[1][0][7] - worker.calls[1][0][6] == 240
    state = next(iter(worker.stored["stop_rechecks"].values()))
    assert state["status"] == "exhausted" and state["blocked_edge"] == 1200
    resumed = {**worker.job, "result": json.dumps(worker.stored)}
    with pytest.raises(ValueError, match="one short stop recheck"):
        activities.continue_inspection(resumed, lambda: False, lambda *args: None)
    assert len(worker.calls) == 3


def test_recheck_cannot_merge_adjacent_disjoint_action(worker):
    _premature_stop(worker)
    worker.rows[1] = interval(800, 900)
    with pytest.raises(ValueError, match="continuity"):
        activities.continue_inspection(worker.job, lambda: False, lambda *args: None)
    activity = worker.stored["visual_results"][0]["activity"]
    assert activity["end_frame"] == 715 and not activity["complete"]
    assert len(worker.calls) == 2


def test_recheck_uncertainty_stops_without_automatic_probe_loop(worker):
    _premature_stop(worker)
    worker.rows[1] = {**interval(685, 715, after=True), "boundary_conflict_after": True}
    worker.outcomes[1] = "uncertain"
    with pytest.raises(ValueError, match="after its short recheck"):
        activities.continue_inspection(worker.job, lambda: False, lambda *args: None)
    assert len(worker.calls) == 2
    assert not worker.stored["visual_results"][0]["activity"]["complete"]
    resumed = {**worker.job, "result": json.dumps(worker.stored)}
    with pytest.raises(ValueError, match="after its short recheck"):
        activities.continue_inspection(resumed, lambda: False, lambda *args: None)
    assert len(worker.calls) == 2


def test_probe_quota_failure_retains_partial_and_retry_skips_long_request(
    worker, monkeypatch
):
    _premature_stop(worker)
    original = grounding.inspect_continuation

    def inspect(query, spec, **kwargs):
        if len(worker.calls) == 1:
            worker.calls.append([spec])
            return {}, ValueError("quota")
        return original(query, spec, **kwargs)

    monkeypatch.setattr(grounding, "inspect_continuation", inspect)
    with pytest.raises(ValueError):
        activities.continue_inspection(worker.job, lambda: False, lambda *args: None)
    assert worker.stored["visual_results"][0]["activity"]["end_frame"] == 715
    assert not worker.stored["visual_results"][0]["activity"]["complete"]
    monkeypatch.setattr(grounding, "inspect_continuation", original)
    resumed = {**worker.job, "result": json.dumps(worker.stored)}
    output = activities.continue_inspection(resumed, lambda: False, lambda *args: None)
    assert len(worker.calls) == 3
    assert worker.calls[-1][0][6:] == (685, 900)
    assert output["visual_results"][0]["activity"]["complete"]


def test_cancelled_verified_probe_is_reused_without_another_call(worker):
    _premature_stop(worker)
    with pytest.raises(media.Cancelled):
        activities.continue_inspection(
            worker.job, lambda: len(worker.calls) >= 2, lambda *args: None
        )
    saved = copy.deepcopy(worker.stored)
    assert saved["visual_results"][0]["activity"]["end_frame"] == 715
    assert not saved["visual_results"][0]["activity"]["complete"]
    assert next(iter(saved["stop_rechecks"].values()))["status"] == "verified"
    resumed = {**worker.job, "result": json.dumps(saved)}
    output = activities.continue_inspection(resumed, lambda: False, lambda *args: None)
    assert len(worker.calls) == 2
    assert output["visual_results"][0]["activity"]["end_frame"] == 900
    assert output["visual_results"][0]["activity"]["complete"]


def test_specific_move_stop_does_not_add_probe(worker):
    _premature_stop(worker, intent="specific_move")
    output = activities.continue_inspection(
        worker.job, lambda: False, lambda *args: None
    )
    assert len(worker.calls) == 1
    assert output["visual_results"][0]["activity"]["end_frame"] == 715
    assert not output["stop_rechecks"]


def test_source_edge_stop_does_not_add_probe(worker):
    _premature_stop(worker)
    worker.rows = [interval(75, 900)]
    output = activities.continue_inspection(
        worker.job, lambda: False, lambda *args: None
    )
    assert len(worker.calls) == 1
    assert output["visual_results"][0]["activity"]["complete"]


def test_before_stop_recheck_is_directional_and_bounded(worker):
    _premature_stop(worker)
    payload = json.loads(worker.job["payload"])
    payload["candidates"] = [result(interval(600, 900, before=True))]
    worker.job["payload"] = json.dumps(payload)
    worker.rows = [interval(185, 720), interval(0, 215)]
    output = activities.continue_inspection(
        worker.job, lambda: False, lambda *args: None
    )
    spec = worker.calls[1][0]
    assert spec[3:5] == (185, 215)
    assert spec[6:] == (0, 215)
    assert worker.requests[1]["direction"] == "before"
    activity = output["visual_results"][0]["activity"]
    assert activity["start_frame"] == 0 and activity["end_frame"] == 900
    assert activity["complete"]
