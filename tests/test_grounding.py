"""Provider-boundary regressions; never call Gemini or prepare real media."""

import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from server import ai, config, grounding


def candidate(ident="a", context_start=300, context_end=540, asset_frames=1200):
    return (
        ident,
        Path("/opaque.mp4"),
        "hash-" + ident,
        context_start + 30,
        context_start + 90,
        asset_frames,
        context_start,
        context_end,
    )


def row(ident="a"):
    return {
        "candidate_id": ident,
        "intent": "specific_move",
        "requested_duration_seconds": None,
        "decision": "match",
        "intervals": [
            {
                "start_seconds": 0.5,
                "end_seconds": 3.2,
                "suggested_start_seconds": 0.5,
                "suggested_end_seconds": 3.2,
                "visible_evidence": "The athlete plants a foot, kicks, and lands.",
                "continues_before": False,
                "continues_after": False,
            }
        ],
    }


@pytest.fixture
def fake(monkeypatch):
    state = SimpleNamespace(
        cache={}, calls=[], ledger=[], closed=0, rows=[row()], failure=None, prepared=[]
    )
    state.real_generate = ai._generate_with_unpaid_503_retry
    monkeypatch.setattr(
        grounding.db, "cache_get", lambda key: copy.deepcopy(state.cache.get(key))
    )
    monkeypatch.setattr(
        grounding.db,
        "cache_set",
        lambda key, value: state.cache.__setitem__(key, copy.deepcopy(value)),
    )
    monkeypatch.setattr(
        grounding.db,
        "reserve",
        lambda *args: state.ledger.append(args) or "reservation",
    )
    monkeypatch.setattr(
        grounding.db, "execute", lambda *args: state.ledger.append(args)
    )
    monkeypatch.setattr(
        grounding,
        "verification_clip",
        lambda *args: state.prepared.append(args) or b"video",
    )

    def close():
        state.closed += 1

    def generate(api, **kwargs):
        on_attempt = kwargs.pop("on_attempt", None)
        if on_attempt is not None:
            on_attempt()
        state.calls.append(kwargs)
        if state.failure:
            raise state.failure
        return SimpleNamespace(
            text=json.dumps({"results": state.rows}), usage_metadata=None
        )

    monkeypatch.setattr(ai, "embedding_client", lambda: SimpleNamespace(close=close))
    monkeypatch.setattr(ai, "_generate_with_unpaid_503_retry", generate)
    return state


def test_single_combined_request_maps_local_seconds_without_padding(fake):
    results, error = grounding.inspect_ranges("a kick", [candidate()], job_id="job")
    assert error is None
    interval = results["a"]["intervals"][0]
    assert (interval["start_frame"], interval["end_frame"]) == (315, 396)
    assert interval["suggested_end_frame"] == 396  # No unconditional follow-through.
    assert len(fake.calls) == fake.closed == 1
    assert fake.ledger[0][0] == "job"
    assert fake.calls[0]["config"].response_schema["properties"]["results"]
    grounding.inspect_ranges("a kick", [candidate()])
    assert len(fake.calls) == 1


def test_budget_failure_is_actionable_without_dispatching_or_leaking_details(fake, monkeypatch):
    def exhausted(*_args):
        raise ValueError("Untrusted internal accounting details")

    monkeypatch.setattr(grounding.db, "reserve", exhausted)
    diagnostics = {}
    results, error = grounding.inspect_ranges("kick", [candidate()], diagnostics=diagnostics)
    assert not results and error.inspection_code == "budget_unavailable"
    assert "Cached results and manual editing remain available" in error.safe_message
    assert "Untrusted" not in error.safe_message
    assert diagnostics["error_code"] == "budget_unavailable"
    assert not fake.calls


def test_batch_validates_candidates_independently_and_caches_valid_work(fake):
    fake.rows = [row(), row("b")]
    fake.rows[1]["intervals"][0]["end_seconds"] = 100
    results, error = grounding.inspect_ranges("kick", [candidate(), candidate("b")])
    assert set(results) == {"a"} and error is not None
    assert len(fake.cache) == 1
    fake.rows = [row("b")]
    results, error = grounding.inspect_ranges("kick", [candidate(), candidate("b")])
    assert set(results) == {"a", "b"} and error is None
    assert fake.prepared[-1][0] == Path("/opaque.mp4")
    assert len(fake.calls[-1]["contents"]) == 3  # Only uncached b is sent.


@pytest.mark.parametrize(
    "change", ["query", "proxy", "anchor", "context", "source", "model", "version"]
)
def test_cache_identity_isolated(fake, monkeypatch, change):
    values = list(candidate())
    original = grounding.cache_key("kick", grounding.InspectionCandidate(*values))
    query = "kick"
    if change == "query":
        query = "punch"
    elif change == "proxy":
        values[2] = "new-hash"
    elif change == "anchor":
        values[3] += 1
    elif change == "context":
        values[6] -= 1
    elif change == "source":
        values[5] += 1
    elif change == "model":
        monkeypatch.setattr(config, "VISUAL_VERIFIER_MODEL", "different-model")
    else:
        monkeypatch.setattr(grounding, "VERSION", "next-version")
    assert (
        grounding.cache_key(query, grounding.InspectionCandidate(*values)) != original
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("start_seconds", True),
        ("start_seconds", "0"),
        ("start_seconds", -1),
        ("end_seconds", float("nan")),
        ("end_seconds", float("inf")),
        ("end_seconds", 9),
        ("end_seconds", 0.2),
        ("suggested_start_seconds", 4),
        ("suggested_end_seconds", 5),
        ("visible_evidence", " "),
        ("continues_after", "false"),
    ],
)
def test_invalid_provider_ranges_fail_closed(fake, field, value):
    fake.rows[0]["intervals"][0][field] = value
    results, error = grounding.inspect_ranges("kick", [candidate()])
    assert results == {} and error is not None
    assert fake.cache == {}


def test_far_away_occurrence_is_rejected(fake):
    values = list(candidate(context_end=1200))
    fake.rows[0]["intervals"][0].update(
        start_seconds=20,
        end_seconds=23,
        suggested_start_seconds=20,
        suggested_end_seconds=23,
    )
    results, error = grounding.inspect_ranges("kick", [values])
    assert results == {} and error is not None


def test_missing_id_preserves_independent_match(fake):
    results, error = grounding.inspect_ranges("kick", [candidate(), candidate("b")])
    assert set(results) == {"a"} and error is not None


def test_duplicate_id_is_not_a_match(fake):
    fake.rows = [row(), row()]
    results, error = grounding.inspect_ranges("kick", [candidate()])
    assert results == {} and error is not None


def test_invalid_sibling_id_does_not_discard_valid_work(fake):
    fake.rows.append({"candidate_id": ["not", "an", "id"]})
    results, error = grounding.inspect_ranges("kick", [candidate(), candidate("b")])
    assert set(results) == {"a"} and error is not None


@pytest.mark.parametrize("before,after", [(True, False), (False, True), (True, True)])
def test_conflicting_continuation_retains_local_match_as_unresolved(
    fake, before, after
):
    fake.rows[0]["intervals"][0].update(continues_before=before, continues_after=after)
    metrics = {}
    results, error = grounding.inspect_ranges(
        "kick", [candidate()], diagnostics=metrics
    )
    assert error is None and metrics["error_code"] is None
    interval = results["a"]["intervals"][0]
    assert (interval["start_frame"], interval["end_frame"]) == (315, 396)
    assert interval["boundary_conflict_before"] is before
    assert interval["boundary_conflict_after"] is after
    assert interval["continues_before"] is before
    assert interval["continues_after"] is after
    assert metrics["candidates"][0]["status"] == "validated"
    assert metrics["errors"][0]["code"] == "boundary_conflict"
    assert metrics["errors"][0]["fatal"] is False
    assert metrics["errors"][0]["proposed_interval"] == {
        "start_seconds": 0.5,
        "end_seconds": 3.2,
        "suggested_start_seconds": 0.5,
        "suggested_end_seconds": 3.2,
        "continues_before": before,
        "continues_after": after,
        "boundary_conflict_before": before,
        "boundary_conflict_after": after,
    }
    cached, error = grounding.inspect_ranges("kick", [candidate()], diagnostics=metrics)
    assert error is None and cached == results and len(fake.calls) == 1
    assert metrics["cache_hits"] == 1 and metrics["error_code"] is None
    assert metrics["errors"][0]["proposed_interval"]["start_frame"] == 315


def test_size_limit_prevents_request_and_reservation(fake, monkeypatch):
    monkeypatch.setattr(grounding, "verification_clip", lambda *args: b"v" * 80_000_001)
    results, error = grounding.inspect_ranges("kick", [candidate()])
    assert results == {} and error is not None
    assert not fake.calls and not fake.ledger


def test_cache_validation_cannot_bypass_bounds(fake):
    grounding.inspect_ranges("kick", [candidate()])
    key = next(iter(fake.cache))
    fake.cache[key]["intervals"][0]["end_frame"] = 9000
    fake.rows = [
        {
            "candidate_id": "a",
            "intent": "specific_move",
            "requested_duration_seconds": None,
            "decision": "no_match",
            "intervals": [],
        }
    ]
    results, error = grounding.inspect_ranges("kick", [candidate()])
    assert error is None and results["a"]["decision"] == "no_match"
    assert len(fake.calls) == 2


def test_provider_failure_retains_cached_match_and_sanitizes_error(fake):
    grounding.inspect_ranges("kick", [candidate()])

    class QuotaError(Exception):
        code = 429
        message = "api_key=secret /Users/person/private/video.mp4 quota exhausted"

    fake.failure = QuotaError()
    results, error = grounding.inspect_ranges("kick", [candidate(), candidate("b")])
    assert set(results) == {"a"}
    assert error.status_code == 429
    assert "secret" not in str(error) and "/Users/person" not in str(error)
    assert "rejected" in fake.ledger[-1][0]
    assert fake.closed == 2


def test_cancel_before_call_retains_cached_work(fake):
    grounding.inspect_ranges("kick", [candidate()])
    results, error = grounding.inspect_ranges(
        "kick", [candidate(), candidate("b")], cancelled=lambda: True
    )
    assert set(results) == {"a"} and isinstance(error, InterruptedError)
    assert len(fake.calls) == 1


def test_cancellation_during_call_saves_completed_inspection(fake):
    results, error = grounding.inspect_ranges(
        "kick", [candidate()], cancelled=lambda: bool(fake.calls)
    )
    assert set(results) == {"a"} and isinstance(error, InterruptedError)
    assert len(fake.cache) == 1


def test_source_bounds_force_continuation_false(fake):
    fake.rows[0]["intervals"][0].update(
        start_seconds=0,
        end_seconds=8,
        suggested_start_seconds=0,
        suggested_end_seconds=5,
        continues_before=True,
        continues_after=True,
    )
    results, error = grounding.inspect_ranges(
        "boxing", [candidate(context_start=0, context_end=240, asset_frames=240)]
    )
    assert error is None
    interval = results["a"]["intervals"][0]
    assert not interval["continues_before"] and not interval["continues_after"]


@pytest.mark.parametrize("intent", ["broad_activity", "specific_move"])
@pytest.mark.parametrize("requested", [None, 20])
def test_interior_crop_edges_require_inspection_even_when_model_reports_complete(
    fake, intent, requested
):
    fake.rows[0].update(intent=intent, requested_duration_seconds=requested)
    fake.rows[0]["intervals"][0].update(
        start_seconds=0,
        end_seconds=8,
        suggested_start_seconds=1,
        suggested_end_seconds=4,
        continues_before=False,
        continues_after=False,
    )
    results, error = grounding.inspect_ranges("requested footage", [candidate()])
    assert error is None
    span = results["a"]["intervals"][0]
    assert span["continues_before"] and span["continues_after"]
    assert (span["start_frame"], span["end_frame"]) == (300, 540)
    assert "supplied video local seconds 0 to 8.000" in fake.calls[0]["contents"][0]
    # Cached responses pass the same conservative boundary policy.
    key = next(iter(fake.cache))
    fake.cache[key]["intervals"][0].update(
        continues_before=False, continues_after=False
    )
    cached, error = grounding.inspect_ranges("requested footage", [candidate()])
    assert error is None and cached["a"]["intervals"][0]["continues_after"]
    assert len(fake.calls) == 1


@pytest.mark.parametrize("start,end,expected", [(0.3, 7.7, True), (0.4, 7.6, False)])
def test_crop_edge_tolerance_matches_one_sampled_frame(fake, start, end, expected):
    fake.rows[0]["intervals"][0].update(
        start_seconds=start,
        end_seconds=end,
        suggested_start_seconds=1,
        suggested_end_seconds=4,
    )
    results, error = grounding.inspect_ranges("activity", [candidate()])
    assert error is None
    span = results["a"]["intervals"][0]
    assert span["continues_before"] is expected
    assert span["continues_after"] is expected


def test_activity_end_inside_context_does_not_absorb_following_action(fake):
    fake.rows[0]["intervals"][0].update(
        start_seconds=1,
        end_seconds=3,
        suggested_start_seconds=1,
        suggested_end_seconds=3,
    )
    results, error = grounding.inspect_ranges("activity", [candidate()])
    assert error is None
    span = results["a"]["intervals"][0]
    assert not span["continues_before"] and not span["continues_after"]
    assert span["end_frame"] == 390


def test_duration_and_separate_occurrences(fake):
    first = fake.rows[0]
    first.update(intent="broad_activity", requested_duration_seconds=20)
    first["intervals"][0].update(
        start_seconds=0,
        end_seconds=2,
        suggested_start_seconds=0,
        suggested_end_seconds=2,
    )
    other = copy.deepcopy(first["intervals"][0])
    other.update(
        start_seconds=4,
        end_seconds=6,
        suggested_start_seconds=4,
        suggested_end_seconds=6,
    )
    first["intervals"].append(other)
    results, error = grounding.inspect_ranges("20 seconds of boxing", [candidate()])
    assert error is None and len(results["a"]["intervals"]) == 2
    assert results["a"]["requested_duration_seconds"] == 20


@pytest.mark.parametrize(
    "values",
    [
        [],
        [candidate()] * 6,
        [candidate(), candidate()],
        [candidate(context_end=1201)],
        [("a", Path("/x"), "hash", 0, 900, 901, 0, 901)],
    ],
)
def test_invalid_input_makes_no_provider_call(fake, values):
    results, error = grounding.inspect_ranges("kick", values)
    assert results == {} and error is not None and not fake.calls


def test_diagnostics_controlled_clock_and_cached_zero_requests(fake, monkeypatch):
    clock = iter([10.0, 12.5, 20.0, 20.125])
    monkeypatch.setattr(grounding.time, "perf_counter", lambda: next(clock))
    monkeypatch.setattr(config, "VISUAL_TIER", "unpaid")
    metrics = {}
    _, error = grounding.inspect_ranges("kick", [candidate()], diagnostics=metrics)
    assert error is None
    assert metrics["elapsed_seconds"] == 2.5
    assert metrics["request_attempts"] == 1 and metrics["retries"] == 0
    assert metrics["submitted_video_seconds"] == 8
    assert metrics["cache_hits"] == 0
    assert metrics["estimated_usd"] == 0 and not metrics["usage_available"]
    _, error = grounding.inspect_ranges("kick", [candidate()], diagnostics=metrics)
    assert error is None
    assert metrics["elapsed_seconds"] == 0.125 and metrics["cache_hits"] == 1
    assert metrics["request_attempts"] == metrics["submitted_video_seconds"] == 0


def test_diagnostics_counts_actual_503_retry_and_token_usage(fake, monkeypatch):
    class CapacityError(Exception):
        code = 503

    attempts = []

    def generate_content(**kwargs):
        assert "on_attempt" not in kwargs
        attempts.append(kwargs)
        if len(attempts) == 1:
            raise CapacityError()
        return SimpleNamespace(
            text=json.dumps({"results": [row()]}),
            usage_metadata=SimpleNamespace(
                prompt_token_count=200,
                candidates_token_count=30,
                thoughts_token_count=10,
            ),
        )

    monkeypatch.setattr(ai, "_generate_with_unpaid_503_retry", fake.real_generate)
    monkeypatch.setattr(
        ai,
        "embedding_client",
        lambda: SimpleNamespace(
            models=SimpleNamespace(generate_content=generate_content),
            close=lambda: None,
        ),
    )
    monkeypatch.setattr(ai.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(config, "VISUAL_TIER", "unpaid")
    metrics = {}
    results, error = grounding.inspect_ranges(
        "kick", [candidate()], diagnostics=metrics
    )
    assert error is None and "a" in results
    assert metrics["request_attempts"] == 2 and metrics["retries"] == 1
    assert metrics["submitted_video_seconds"] == 16
    assert (
        metrics["input_tokens"],
        metrics["output_tokens"],
        metrics["thinking_tokens"],
    ) == (200, 30, 10)
    assert metrics["usage_available"] and metrics["estimated_usd"] == 0


@pytest.mark.parametrize("exit_mode", ["cancel", "invalid", "quota"])
def test_diagnostics_always_record_early_exits(fake, monkeypatch, exit_mode):
    clock = iter([5.0, 6.0])
    monkeypatch.setattr(grounding.time, "perf_counter", lambda: next(clock))
    metrics = {}

    class QuotaError(Exception):
        code = 429

    if exit_mode == "quota":
        fake.failure = QuotaError("quota")
    _, error = grounding.inspect_ranges(
        "kick",
        [] if exit_mode == "invalid" else [candidate()],
        cancelled=lambda: exit_mode == "cancel",
        diagnostics=metrics,
    )
    assert error is not None and metrics["elapsed_seconds"] == 1
    assert metrics["request_attempts"] == (1 if exit_mode == "quota" else 0)


def test_paid_diagnostics_report_usage_cost_without_changing_tier(fake, monkeypatch):
    monkeypatch.setattr(config, "VISUAL_TIER", "paid")
    metrics = {}
    grounding.inspect_ranges("kick", [candidate()], diagnostics=metrics)
    assert metrics["estimated_usd"] > 0
    assert metrics["request_attempts"] == 1 and config.VISUAL_TIER == "paid"


@pytest.mark.parametrize(
    "field,value,code",
    [
        ("start_seconds", -1, "timestamp_out_of_context"),
        ("end_seconds", float("nan"), "timestamp_out_of_context"),
        ("end_seconds", 0.2, "interval_invalid"),
        ("visible_evidence", " ", "evidence_invalid"),
    ],
)
def test_validation_codes_preserve_safe_reason_and_valid_sibling(
    fake, field, value, code
):
    fake.rows = [row(), row("b")]
    fake.rows[1]["intervals"][0][field] = value
    metrics = {}
    results, error = grounding.inspect_ranges(
        "kick", [candidate(), candidate("b")], diagnostics=metrics
    )
    assert set(results) == {"a"} and len(fake.cache) == 1
    assert isinstance(error, ValueError) and error.code == code
    assert error.safe_message == str(error)
    assert metrics["error_code"] == code
    event = dict(metrics["errors"][0])
    snapshot = event.pop("proposed_interval")
    assert event == {"candidate_id": "b", "stage": "range_validation", "code": code}
    assert snapshot["suggested_start_seconds"] == 0.5
    assert "visible_evidence" not in snapshot
    json.dumps(metrics, allow_nan=False)
    assert metrics["candidates"][0]["status"] == "validated"
    assert metrics["candidates"][1]["error_code"] == code


def test_manifest_is_bounded_private_and_stable_for_cached_work(fake):
    specs = [candidate(str(index)) for index in range(5)]
    fake.rows = [row(str(index)) for index in range(5)]
    metrics = {}
    _, error = grounding.inspect_ranges("private query", specs, diagnostics=metrics)
    assert error is None and len(metrics["candidates"]) == 5
    assert metrics["candidates"][0] == {
        "candidate_id": "0",
        "proxy_fingerprint": grounding.hashlib.sha256(b"hash-0").hexdigest(),
        "anchor_start_frame": 330,
        "anchor_end_frame": 390,
        "context_start_frame": 300,
        "context_end_frame": 540,
        "asset_frames": 1200,
        "sample_fps": 3,
        "status": "validated",
    }
    serialized = json.dumps(metrics)
    assert "private query" not in serialized and "/opaque.mp4" not in serialized
    assert "hash-0" not in serialized and "plants a foot" not in serialized
    assert len(metrics["batch_fingerprint"]) == 64
    original_fingerprint = metrics["batch_fingerprint"]
    _, error = grounding.inspect_ranges("private query", specs, diagnostics=metrics)
    assert error is None and metrics["cache_hits"] == 5
    assert all(item["status"] == "cached" for item in metrics["candidates"])
    assert metrics["batch_fingerprint"] is None  # No actual dispatch batch.
    fake.cache.clear()
    grounding.inspect_ranges("private query", specs, diagnostics=metrics)
    assert metrics["batch_fingerprint"] == original_fingerprint
    fake.cache.clear()
    grounding.inspect_ranges(
        "private query", list(reversed(specs)), diagnostics=metrics
    )
    assert metrics["batch_fingerprint"] != original_fingerprint


def test_five_invalid_siblings_each_keep_code_with_bounded_errors(fake):
    fake.rows = [row(str(index)) for index in range(5)]
    for entry in fake.rows:
        entry["intervals"][0]["end_seconds"] = 999
    # An unknown provider ID is never copied into diagnostics.
    fake.rows.append({"candidate_id": "/Users/private/api_key=secret"})
    metrics = {}
    results, error = grounding.inspect_ranges(
        "kick", [candidate(str(index)) for index in range(5)], diagnostics=metrics
    )
    assert not results and error is not None
    assert metrics["error_count"] == 6 and len(metrics["errors"]) == 5
    assert all(
        item["error_code"] == "timestamp_out_of_context"
        for item in metrics["candidates"]
    )
    assert "secret" not in json.dumps(metrics)


@pytest.mark.parametrize("kind", ["missing", "duplicate", "unknown", "malformed"])
def test_response_structure_has_stable_codes_and_retains_siblings(fake, kind):
    fake.rows = [row()]
    expected = "candidate_missing"
    if kind == "duplicate":
        fake.rows.extend([row("b"), row("b")])
        expected = "candidate_duplicate"
    elif kind == "unknown":
        fake.rows.extend([row("b"), row("/private/secret")])
        expected = "candidate_set_invalid"
    elif kind == "malformed":
        fake.rows = None
        expected = "response_malformed"
    metrics = {}
    results, error = grounding.inspect_ranges(
        "kick", [candidate(), candidate("b")], diagnostics=metrics
    )
    assert error.inspection_code == metrics["error_code"] == expected
    assert ("a" in results) is (kind != "malformed")
    assert "secret" not in json.dumps(metrics)


def test_provider_error_diagnostics_and_message_exclude_raw_text(fake):
    class QuotaError(Exception):
        code = 429
        message = "arbitrary_secret api_key=secret /Users/private/video.mp4"

    fake.failure = QuotaError()
    metrics = {}
    _, error = grounding.inspect_ranges("kick", [candidate()], diagnostics=metrics)
    assert error.status_code == error.code == 429
    assert error.inspection_code == metrics["error_code"] == "provider_failure"
    assert metrics["errors"] == [
        {"code": "provider_failure", "stage": "provider_request", "status_code": 429}
    ]
    assert "quota or rate limit" in error.safe_message
    assert "secret" not in str(error) + json.dumps(metrics)


def test_recovered_cache_failure_is_observable_without_changing_acceptance(fake):
    grounding.inspect_ranges("kick", [candidate()])
    key = next(iter(fake.cache))
    fake.cache[key]["intervals"][0]["end_frame"] = 9000
    metrics = {}
    results, error = grounding.inspect_ranges(
        "kick", [candidate()], diagnostics=metrics
    )
    assert error is None and "a" in results and len(fake.calls) == 2
    event = dict(metrics["errors"][0])
    snapshot = event.pop("proposed_interval")
    assert event == {
        "candidate_id": "a",
        "stage": "cache_validation",
        "code": "interval_invalid",
    }
    assert snapshot["end_frame"] == 9000
    assert metrics["error_code"] is None
    assert metrics["candidates"][0]["status"] == "validated"
    assert "error_code" not in metrics["candidates"][0]


def test_cancel_retains_type_and_stable_diagnostics(fake):
    metrics = {}
    _, error = grounding.inspect_ranges(
        "kick", [candidate()], cancelled=lambda: True, diagnostics=metrics
    )
    assert isinstance(error, InterruptedError)
    assert error.inspection_code == metrics["error_code"] == "cancelled"
    assert metrics["request_attempts"] == 0


def test_malformed_json_and_returned_model_are_observable_without_raw_text(
    fake, monkeypatch
):
    def generate(api, **kwargs):
        kwargs["on_attempt"]()
        return SimpleNamespace(
            text="malformed private response api_key=secret",
            model_version="gemini-test-version",
            usage_metadata=None,
        )

    monkeypatch.setattr(ai, "_generate_with_unpaid_503_retry", generate)
    metrics = {}
    results, error = grounding.inspect_ranges(
        "private query", [candidate()], diagnostics=metrics
    )
    assert not results and error.inspection_code == "response_malformed"
    assert metrics["returned_model_version"] == "gemini-test-version"
    assert "private" not in json.dumps(metrics) and "secret" not in str(error)
    assert fake.closed == 1


def test_untrusted_request_identity_is_fingerprinted_in_diagnostics(fake):
    ident = "/Users/private/api_key=secret"
    fake.rows = [row(ident)]
    metrics = {}
    results, error = grounding.inspect_ranges(
        "kick", [candidate(ident)], diagnostics=metrics
    )
    assert error is None and ident in results
    assert metrics["candidates"][0]["candidate_id"].startswith("sha256:")
    assert "secret" not in json.dumps(metrics)


@pytest.mark.parametrize(
    "problem,expected",
    [
        ("intent", "intent_invalid"),
        ("overlap", "occurrences_overlap"),
        ("anchor", "anchor_unrelated"),
    ],
)
def test_remaining_validation_reasons_are_stable(fake, problem, expected):
    specs = [candidate()]
    if problem == "intent":
        fake.rows[0]["intent"] = "unknown"
    elif problem == "overlap":
        fake.rows[0]["intervals"].append(copy.deepcopy(fake.rows[0]["intervals"][0]))
    else:
        specs = [candidate(context_end=1200)]
        fake.rows[0]["intervals"][0].update(
            start_seconds=20,
            end_seconds=23,
            suggested_start_seconds=20,
            suggested_end_seconds=23,
        )
    metrics = {}
    results, error = grounding.inspect_ranges("kick", specs, diagnostics=metrics)
    assert not results and error.inspection_code == metrics["error_code"] == expected


@pytest.mark.parametrize("status", ["RESOURCE_EXHAUSTED", "secret_provider_status"])
def test_provider_status_uses_fixed_category_allowlist(fake, status):
    class QuotaError(Exception):
        code = 429

    fake.failure = QuotaError("secret raw message")
    fake.failure.status = status
    metrics = {}
    _, error = grounding.inspect_ranges("kick", [candidate()], diagnostics=metrics)
    expected = status if status == "RESOURCE_EXHAUSTED" else None
    assert error.provider_status == expected
    assert metrics["errors"][-1].get("provider_status") == expected
    assert "secret" not in json.dumps(metrics) + str(error)


@pytest.mark.parametrize("intent", ["broad_activity", "specific_move"])
@pytest.mark.parametrize("requested", [None, 0.5, 20])
def test_edit_duration_is_nullable_positive_and_independent_of_action(
    fake, intent, requested
):
    fake.rows[0].update(intent=intent, requested_duration_seconds=requested)
    results, error = grounding.inspect_ranges("requested footage", [candidate()])
    assert error is None
    assert results["a"]["intent"] == intent
    assert results["a"]["requested_duration_seconds"] == requested


@pytest.mark.parametrize("requested", [0, -1, True, "20", float("nan"), float("inf")])
def test_invalid_independent_edit_duration_keeps_safe_validation(fake, requested):
    fake.rows[0].update(intent="broad_activity", requested_duration_seconds=requested)
    results, error = grounding.inspect_ranges("requested footage", [candidate()])
    assert not results and error.inspection_code == "intent_invalid"
    assert not fake.cache


def test_v3_schema_has_action_intents_and_independent_edit_duration():
    schema = grounding._schema()["properties"]["results"]["items"]
    assert schema["properties"]["intent"]["enum"] == ["broad_activity", "specific_move"]
    assert schema["properties"]["requested_duration_seconds"] == {
        "type": "NUMBER",
        "nullable": True,
    }
    assert "requested_duration_seconds" in schema["required"]


def test_short_crop_duration_pairing_preserves_recognition_plumbing(fake):
    # This exercises the contract with controlled replies, not Gemini accuracy.
    fake.rows[0].update(intent="broad_activity")
    fake.rows[0]["intervals"][0].update(
        start_seconds=0,
        end_seconds=8,
        suggested_start_seconds=0,
        suggested_end_seconds=5,
        visible_evidence="The boxer is throwing punches.",
    )
    plain, error = grounding.inspect_ranges("boxing", [candidate()])
    assert error is None
    fake.rows[0]["requested_duration_seconds"] = 20
    requested, error = grounding.inspect_ranges("20 seconds of boxing", [candidate()])
    assert error is None
    assert plain["a"]["intervals"] == requested["a"]["intervals"]
    assert requested["a"]["intent"] == "broad_activity"
    assert requested["a"]["requested_duration_seconds"] == 20
    assert requested["a"]["intervals"][0]["end_frame"] == 540
    assert len(fake.calls) == 2  # One existing inspection per distinct query.
    call = fake.calls[-1]
    prompt = call["contents"][-1]
    assert prompt.endswith(json.dumps("20 seconds of boxing"))
    assert "An eight-second crop visibly showing boxing can match" in prompt
    assert "Do not invent or extend timestamps" in prompt
    assert call["contents"][1].video_metadata.fps == 3
    assert call["config"].temperature == 0


@pytest.mark.parametrize(
    "query", ["a person holds a plank for 20 seconds", "a 20-second plank"]
)
def test_action_duration_or_ambiguous_condition_remains_semantic_requirement(
    fake, query
):
    # An eight-second crop cannot prove a twenty-second action condition.
    fake.rows[0].update(
        intent="broad_activity",
        requested_duration_seconds=None,
        decision="uncertain",
        intervals=[],
    )
    results, error = grounding.inspect_ranges(query, [candidate()])
    assert error is None
    assert results["a"]["decision"] == "uncertain"
    assert results["a"]["requested_duration_seconds"] is None
    assert results["a"]["intervals"] == []
    prompt = fake.calls[0]["contents"][-1]
    assert prompt.endswith(json.dumps(query))
    assert "eight seconds of a plank does not establish the condition" in prompt
    assert "edit-length versus action-condition meaning is ambiguous" in prompt
    assert len(fake.calls) == 1


def test_versioned_cache_retains_historical_entries_without_reusing_old_decisions(
    fake, monkeypatch
):
    original_version = grounding.VERSION
    spec = grounding.InspectionCandidate(*candidate())
    monkeypatch.setattr(grounding, "VERSION", "grounded-ranges-v2-crop-boundaries-3fps")
    old_key = grounding.cache_key("20 seconds of boxing", spec)
    historical = {
        "intent": "duration",
        "requested_duration_seconds": 20,
        "decision": "no_match",
        "intervals": [],
    }
    fake.cache[old_key] = copy.deepcopy(historical)
    monkeypatch.setattr(grounding, "VERSION", original_version)
    assert original_version.startswith("grounded-ranges-v4-")
    assert grounding.cache_key("20 seconds of boxing", spec) != old_key
    fake.rows[0].update(intent="broad_activity", requested_duration_seconds=20)
    results, error = grounding.inspect_ranges("20 seconds of boxing", [candidate()])
    assert error is None and results["a"]["decision"] == "match"
    assert len(fake.calls) == 1 and len(fake.cache) == 2
    assert fake.cache[old_key] == historical
    grounding.inspect_ranges("20 seconds of boxing", [candidate()])
    assert len(fake.calls) == 1  # New contract reuses validated new work.


def test_obsolete_duration_intent_is_rejected_by_v3_contract(fake):
    fake.rows[0].update(intent="duration", requested_duration_seconds=20)
    results, error = grounding.inspect_ranges("20 seconds of boxing", [candidate()])
    assert not results and error.inspection_code == "intent_invalid"


def test_legitimate_interior_stop_needs_no_boundary_conflict(fake):
    metrics = {}
    results, error = grounding.inspect_ranges(
        "kick", [candidate()], diagnostics=metrics
    )
    interval = results["a"]["intervals"][0]
    assert error is None and not metrics["errors"]
    assert (
        not interval["boundary_conflict_before"]
        and not interval["boundary_conflict_after"]
    )
    assert not interval["continues_before"] and not interval["continues_after"]
    # This resolves inspected bounds, not evidence of complete-move quality.
    assert (interval["start_frame"], interval["end_frame"]) == (315, 396)


@pytest.mark.parametrize("value", [9, float("nan"), float("inf"), True, "secret"])
def test_boundary_claim_cannot_bypass_invalid_timestamp(fake, value):
    fake.rows[0]["intervals"][0].update(end_seconds=value, continues_after=True)
    metrics = {}
    results, error = grounding.inspect_ranges(
        "kick", [candidate()], diagnostics=metrics
    )
    assert not results and error.inspection_code == "timestamp_out_of_context"
    assert not fake.cache and metrics["error_code"] == "timestamp_out_of_context"
    snapshot = metrics["errors"][0]["proposed_interval"]
    assert snapshot["continues_after"] is True
    if value == 9:
        assert snapshot["end_seconds"] == 9
    else:
        assert "end_seconds" not in snapshot
    assert "secret" not in json.dumps(metrics, allow_nan=False)


def test_cached_conflict_cannot_become_completed_from_continuation_flag_alone(fake):
    fake.rows[0]["intervals"][0]["continues_after"] = True
    original, error = grounding.inspect_ranges("kick", [candidate()])
    assert error is None
    key = next(iter(fake.cache))
    fake.cache[key]["intervals"][0]["continues_after"] = False
    cached, error = grounding.inspect_ranges("kick", [candidate()])
    assert error is None and cached == original and len(fake.calls) == 1
    assert cached["a"]["intervals"][0]["boundary_conflict_after"]
    assert cached["a"]["intervals"][0]["continues_after"]


@pytest.mark.parametrize("value", [None, "true", 1])
def test_invalid_cached_conflict_flag_is_recomputed(fake, value):
    grounding.inspect_ranges("kick", [candidate()])
    key = next(iter(fake.cache))
    fake.cache[key]["intervals"][0]["boundary_conflict_after"] = value
    metrics = {}
    results, error = grounding.inspect_ranges(
        "kick", [candidate()], diagnostics=metrics
    )
    assert error is None and "a" in results and len(fake.calls) == 2
    assert metrics["errors"][0]["code"] == "cached_boundary_invalid"
    assert not results["a"]["intervals"][0]["boundary_conflict_after"]


def test_conflict_diagnostics_stay_bounded_numeric_and_nonfatal(fake):
    fake.rows = [row(str(index)) for index in range(5)]
    for entry in fake.rows:
        first = entry["intervals"][0]
        first.update(
            end_seconds=2,
            suggested_end_seconds=2,
            continues_before=True,
            continues_after=True,
        )
        second = copy.deepcopy(first)
        second.update(
            start_seconds=4,
            end_seconds=6,
            suggested_start_seconds=4,
            suggested_end_seconds=6,
        )
        entry["intervals"].append(second)
        first["visible_evidence"] = second["visible_evidence"] = (
            "private evidence secret"
        )
    metrics = {}
    results, error = grounding.inspect_ranges(
        "private query",
        [candidate(str(index)) for index in range(5)],
        diagnostics=metrics,
    )
    assert error is None and len(results) == 5 and metrics["error_code"] is None
    assert metrics["error_count"] == 10 and len(metrics["errors"]) == 5
    assert all(item["status"] == "validated" for item in metrics["candidates"])
    for event in metrics["errors"]:
        assert event["code"] == "boundary_conflict" and event["fatal"] is False
        snapshot = event["proposed_interval"]
        assert sum(type(value) in (int, float) for value in snapshot.values()) == 4
        assert all(type(value) in (int, float, bool) for value in snapshot.values())
    serialized = json.dumps(metrics, allow_nan=False)
    assert "private" not in serialized and "secret" not in serialized


def test_second_invalid_occurrence_reports_its_own_proposed_times(fake):
    second = copy.deepcopy(fake.rows[0]["intervals"][0])
    second.update(
        start_seconds=4,
        end_seconds=9,
        suggested_start_seconds=4,
        suggested_end_seconds=6,
    )
    fake.rows[0]["intervals"].append(second)
    metrics = {}
    results, error = grounding.inspect_ranges(
        "kick", [candidate()], diagnostics=metrics
    )
    assert not results and error.inspection_code == "timestamp_out_of_context"
    snapshot = metrics["errors"][0]["proposed_interval"]
    assert snapshot["start_seconds"] == 4 and snapshot["end_seconds"] == 9


def test_v4_retains_v3_cache_without_silently_reusing_its_boundary_policy(
    fake, monkeypatch
):
    current = grounding.VERSION
    spec = grounding.InspectionCandidate(*candidate())
    monkeypatch.setattr(
        grounding, "VERSION", "grounded-ranges-v3-independent-edit-duration-3fps"
    )
    old_key = grounding.cache_key("kick", spec)
    historical = {
        "intent": "specific_move",
        "requested_duration_seconds": None,
        "decision": "no_match",
        "intervals": [],
    }
    fake.cache[old_key] = copy.deepcopy(historical)
    monkeypatch.setattr(grounding, "VERSION", current)
    fake.rows[0]["intervals"][0]["continues_after"] = True
    results, error = grounding.inspect_ranges("kick", [candidate()])
    assert error is None and results["a"]["intervals"][0]["boundary_conflict_after"]
    assert len(fake.calls) == 1 and len(fake.cache) == 2
    assert fake.cache[old_key] == historical


def continuation_activity():
    return {
        "start_frame": 330,
        "end_frame": 390,
        "intent": "broad_activity",
        "requested_frames": 600,
        "visible_evidence": "One athlete continues a boxing combination.",
    }


def continuation_row(**changes):
    value = {
        "candidate_id": "a",
        "continuity": "same_activity",
        "continuity_evidence": "The same athlete keeps punching across the marked overlap, with one brief pause.",
        "boundary_outcome": "observed_stop",
        "intervals": [
            {
                "start_seconds": 1,
                "end_seconds": 6,
                "visible_evidence": "The athlete punches, pauses briefly, resumes punching, then visibly lowers both arms.",
            }
        ],
    }
    value.update(changes)
    return value


def continue_call(fake, **kwargs):
    fake.rows = [continuation_row()]
    fake.rows[0].update(kwargs.pop("response", {}))
    return grounding.inspect_continuation(
        "20 seconds of boxing",
        candidate(),
        established_activity=kwargs.pop("established", continuation_activity()),
        direction=kwargs.pop("direction", "after"),
        **kwargs,
    )


def test_continuation_uses_own_contract_and_locked_interpretation(fake):
    metrics = {}
    results, error = continue_call(fake, diagnostics=metrics)
    assert error is None
    value = results["a"]
    assert value["intent"] == "broad_activity"
    assert value["requested_duration_seconds"] == 20
    assert value["continuity"] == "same_activity"
    assert value["intervals"][0]["end_frame"] == 480
    assert not value["intervals"][0]["continues_after"]
    assert metrics["contract_version"] == grounding.CONTINUATION_VERSION
    assert metrics["candidates"][0]["direction"] == "after"
    request = fake.calls[0]
    prompt = request["contents"][-1]
    assert '"locked_intent": "broad_activity"' in prompt
    assert '"requested_edit_frames": 600' in prompt
    assert '"overlap_local_start_seconds": 1.0' in prompt
    assert "Do not search for another occurrence" in prompt
    properties = request["config"].response_schema["properties"]["results"]["items"][
        "properties"
    ]
    assert "intent" not in properties and "requested_duration_seconds" not in properties
    assert properties["intervals"]["maxItems"] == 1
    cached, error = grounding.inspect_continuation(
        "20 seconds of boxing",
        candidate(),
        established_activity=continuation_activity(),
        direction="after",
    )
    assert error is None and cached == results and len(fake.calls) == 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("continuity", "different_activity"),
        ("continuity", "uncertain"),
        ("continuity_evidence", ""),
        ("continuity_evidence", " "),
        ("continuity_evidence", None),
    ],
)
def test_temporal_overlap_without_semantic_connection_is_rejected(fake, field, value):
    results, error = continue_call(fake, response={field: value})
    assert not results and error.inspection_code == "continuity_unsupported"
    assert not fake.cache


@pytest.mark.parametrize("start,end", [(4, 6), (0, 1.5), (1.5, 2.5)])
def test_later_or_incomplete_overlap_cannot_replace_activity(fake, start, end):
    response = continuation_row()
    response["intervals"][0].update(start_seconds=start, end_seconds=end)
    results, error = continue_call(fake, response=response)
    assert not results and error.inspection_code == "continuity_unsupported"


@pytest.mark.parametrize(
    "start,end", [(-0.1, 6), (1, 8.1), (2, 1), (True, 6), (1, float("nan"))]
)
def test_continuation_keeps_strict_timestamp_rejection(fake, start, end):
    response = continuation_row()
    response["intervals"][0].update(start_seconds=start, end_seconds=end)
    results, error = continue_call(fake, response=response)
    assert not results and error is not None and not fake.cache


def test_continuation_uncertain_boundary_stays_partial(fake):
    results, error = continue_call(fake, response={"boundary_outcome": "uncertain"})
    assert error is None
    span = results["a"]["intervals"][0]
    assert span["continues_after"] and span["boundary_conflict_after"]
    assert (span["start_frame"], span["end_frame"]) == (330, 480)


@pytest.mark.parametrize("outcome,end", [("continues", 6), ("observed_stop", 8)])
def test_inconsistent_boundary_outcomes_fail_closed(fake, outcome, end):
    response = continuation_row(boundary_outcome=outcome)
    response["intervals"][0]["end_seconds"] = end
    diagnostics = {}
    results, error = continue_call(fake, response=response, diagnostics=diagnostics)
    assert not results and error.inspection_code == "boundary_conflict"
    detail = diagnostics["errors"][-1]
    assert detail["reason"] == (
        "continuation_edge_missing" if outcome == "continues" else "crop_edge_not_stop"
    )
    assert detail["proposed_interval"]["end_seconds"] == end
    assert detail["proposed_interval"]["boundary_outcome"] == outcome
    assert "continuity_evidence" not in detail["proposed_interval"]


def test_continuation_to_crop_edge_is_partial_until_source_edge(fake):
    response = continuation_row(boundary_outcome="continues")
    response["intervals"][0]["end_seconds"] = 8
    results, error = continue_call(fake, response=response)
    assert error is None and results["a"]["intervals"][0]["continues_after"]
    results, error = grounding.inspect_continuation(
        "20 seconds of boxing",
        candidate(asset_frames=540),
        established_activity=continuation_activity(),
        direction="after",
    )
    assert error is None and not results["a"]["intervals"][0]["continues_after"]


def test_continuation_before_extends_only_the_existing_onset(fake):
    response = continuation_row(boundary_outcome="observed_stop")
    response["intervals"][0].update(start_seconds=0.5, end_seconds=3)
    results, error = continue_call(fake, direction="before", response=response)
    assert error is None
    assert results["a"]["intervals"][0]["start_frame"] == 315
    assert not results["a"]["intervals"][0]["continues_before"]


@pytest.mark.parametrize("direction,start,end", [("after", 1, 2.9), ("before", 1.1, 3)])
def test_observed_stop_cannot_shrink_previously_established_activity(
    fake, direction, start, end
):
    response = continuation_row(boundary_outcome="observed_stop")
    response["intervals"][0].update(start_seconds=start, end_seconds=end)
    results, error = continue_call(fake, direction=direction, response=response)
    assert not results and error.inspection_code == "boundary_conflict"
    assert not fake.cache


@pytest.mark.parametrize("direction,start,end", [("after", 1, 3), ("before", 1, 3)])
def test_observed_stop_may_confirm_the_exact_previously_established_edge(
    fake, direction, start, end
):
    response = continuation_row(boundary_outcome="observed_stop")
    response["intervals"][0].update(start_seconds=start, end_seconds=end)
    results, error = continue_call(fake, direction=direction, response=response)
    assert error is None
    assert not results["a"]["intervals"][0]["continues_" + direction]


@pytest.mark.parametrize(
    "change", ["direction", "intent", "duration", "established", "evidence", "version"]
)
def test_continuation_cache_identity_tracks_contract_and_established_activity(
    fake, monkeypatch, change
):
    spec = grounding.InspectionCandidate(*candidate())
    established = continuation_activity()
    original = grounding.continuation_cache_key("boxing", spec, established, "after")
    discovery = grounding.cache_key("boxing", spec)
    direction = "after"
    if change == "direction":
        direction = "before"
    elif change == "intent":
        established["intent"] = "specific_move"
    elif change == "duration":
        established["requested_frames"] = 90
    elif change == "established":
        established["end_frame"] += 1
    elif change == "evidence":
        established["visible_evidence"] = "Different supported evidence."
    else:
        monkeypatch.setattr(grounding, "CONTINUATION_VERSION", "new-continuation")
    assert (
        grounding.continuation_cache_key("boxing", spec, established, direction)
        != original
    )
    assert grounding.cache_key("boxing", spec) == discovery


def test_continuation_does_not_reuse_general_discovery_cache(fake):
    spec = grounding.InspectionCandidate(*candidate())
    historical = {
        "decision": "no_match",
        "intervals": [],
        "intent": "specific_move",
        "requested_duration_seconds": None,
    }
    fake.cache[grounding.cache_key("20 seconds of boxing", spec)] = historical
    results, error = continue_call(fake)
    assert error is None and results
    assert len(fake.calls) == 1 and len(fake.cache) == 2
    assert fake.cache[grounding.cache_key("20 seconds of boxing", spec)] == historical
