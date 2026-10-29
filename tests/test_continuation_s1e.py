import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from server import grounding as real_grounding

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "continuation_s1e", ROOT / "scripts/evaluate_continuation_s1e.py"
)
s1e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s1e)
EvaluationBudget = s1e.EvaluationBudget
EvaluationLimitReached = s1e.EvaluationLimitReached


def frozen_case():
    return {
        "id": "badminton",
        "input": "data/evaluation/opaque.mp4",
        "sha256": "x" * 64,
        "direction": "after",
        "query": "20 seconds of badminton",
        "anchor": [75, 195],
        "context": [75, 900],
        "asset_frames": 900,
        "activity": {
            "start_frame": 0,
            "end_frame": 195,
            "intent": "broad_activity",
            "requested_frames": 600,
            "visible_evidence": "Visible badminton.",
        },
    }


def provider_row(end=27.5, outcome="continues"):
    return {
        "candidate_id": "c0",
        "continuity": "same_activity",
        "continuity_evidence": "Visible play continues. API_KEY=secret",
        "boundary_outcome": outcome,
        "intervals": [
            {
                "start_seconds": 0,
                "end_seconds": end,
                "visible_evidence": "Visible badminton. /Users/private/key",
            }
        ],
    }


def modules(dispatch):
    sdk = SimpleNamespace(
        models=SimpleNamespace(
            generate_content=dispatch,
            embed_content=lambda **kw: pytest.fail("No embeddings"),
        ),
        close=lambda: None,
    )
    return SimpleNamespace(embedding_client=lambda: sdk), SimpleNamespace(
        verification_clip=lambda proxy, start, end, **kw: f"{start}:{end}".encode()
    )


def part(data):
    return SimpleNamespace(
        inline_data=SimpleNamespace(mime_type="video/mp4", data=data)
    )


def test_safe_snapshot_drops_arbitrary_text_nonfinite_and_extra_fields():
    raw = provider_row()
    raw.update(secret="credential", unknown=123)
    raw["intervals"][0].update(
        start_seconds=float("nan"), requested_duration_seconds=float("inf")
    )
    safe = s1e.safe_response(json.dumps({"results": [raw]}))
    encoded = json.dumps(safe)
    assert "secret" not in encoded
    assert "/Users" not in encoded
    assert "credential" not in encoded
    assert "unknown" not in encoded
    assert "start_seconds" not in safe["results"][0]["intervals"][0]
    assert safe["results"][0]["continuity_evidence_present"]
    assert safe["results"][0]["boundary_outcome"] == "continues"


def test_snapshot_bounds_rows_intervals_and_preserves_invalid_counts():
    raw = provider_row()
    raw["intervals"] *= 10
    safe = s1e.safe_response(json.dumps({"results": [raw] * 12}))
    assert safe["row_count"] == 12
    assert len(safe["results"]) == 5
    assert safe["results"][0]["interval_count"] == 10
    assert len(safe["results"][0]["intervals"]) == 2
    assert len(s1e.restore_for_validation(safe["results"][0])["intervals"]) == 3


def test_offline_replay_identifies_actual_boundary_subtype_without_api():
    row = {
        "case": frozen_case(),
        "purpose": "diagnostic",
        "provider_snapshots": [
            s1e.safe_response(json.dumps({"results": [provider_row(12, "continues")]}))
        ],
    }
    result = s1e.replay(row, real_grounding)
    assert result == {
        "status": "rejected",
        "error_code": "boundary_conflict",
        "reason": "continuation_edge_missing",
        "semantic_revalidation": False,
    }
    row["provider_snapshots"] = [
        s1e.safe_response(json.dumps({"results": [provider_row()]}))
    ]
    accepted = s1e.replay(row, real_grounding)
    assert accepted["status"] == "accepted"
    assert accepted["normalized"]["intervals"][0]["end_frame"] == 900
    assert not accepted["semantic_revalidation"]


def test_reserve_is_durable_before_sdk_and_counts_retries(tmp_path):
    output = tmp_path / "ledger.json"
    report = {"requests": []}
    budget = EvaluationBudget(output, report, 8, 180)
    seen = []

    def dispatch(**kw):
        state = json.loads(output.read_text())["evaluation_budget"]
        seen.append(state["generation_attempts"])
        if len(seen) == 1:
            raise RuntimeError("transient")
        return "ok"

    ai, grounding = modules(dispatch)
    counts = {"video_requests": 0}
    with s1e.bounded_dispatches(ai, grounding, budget, counts, 30):
        video = grounding.verification_clip(None, 0, 180, sample_fps=6)
        client = ai.embedding_client()
        with pytest.raises(RuntimeError):
            client.models.generate_content(contents=[part(video)])
        assert client.models.generate_content(contents=[part(video)]) == "ok"
    assert seen == [1, 2]
    assert report["evaluation_budget"]["supplied_video_seconds"] == 12
    assert counts["video_requests"] == 2


@pytest.mark.parametrize("seconds,successful", [(1, 8), (30, 6)])
def test_shared_caps_cannot_reset_when_a_new_request_or_budget_object_is_created(
    tmp_path, seconds, successful
):
    output = tmp_path / "ledger.json"
    report = {"requests": []}
    seen = []
    ai, grounding = modules(lambda **kw: seen.append(True))
    for index in range(successful):
        budget = EvaluationBudget(output, report, 8, 180)
        with s1e.bounded_dispatches(ai, grounding, budget, {"video_requests": 0}, 30):
            video = grounding.verification_clip(None, 0, seconds * 30)
            ai.embedding_client().models.generate_content(contents=[part(video)])
        report = json.loads(output.read_text())
    budget = EvaluationBudget(output, report, 8, 180)
    with s1e.bounded_dispatches(ai, grounding, budget, {"video_requests": 0}, 30):
        video = grounding.verification_clip(None, 0, seconds * 30)
        with pytest.raises(EvaluationLimitReached):
            ai.embedding_client().models.generate_content(contents=[part(video)])
    assert len(seen) == successful
    assert (
        json.loads(output.read_text())["evaluation_budget"]["generation_attempts"]
        == successful
    )


def test_unknown_video_or_embeddings_cannot_bypass_accounting(tmp_path):
    output = tmp_path / "ledger.json"
    report = {"requests": []}
    budget = EvaluationBudget(output, report, 8, 180)
    ai, grounding = modules(lambda **kw: pytest.fail("No dispatch"))
    with s1e.bounded_dispatches(ai, grounding, budget, {"video_requests": 0}, 30):
        with pytest.raises(ValueError, match="Unaccounted"):
            ai.embedding_client().models.generate_content(contents=[part(b"unknown")])
        with pytest.raises(ValueError, match="do not require embeddings"):
            ai.embedding_client().models.embed_content()
    assert report["evaluation_budget"]["generation_attempts"] == 0


def test_capture_persists_numeric_response_before_validation_can_fail(tmp_path):
    output = tmp_path / "ledger.json"
    report = {"requests": []}
    row = {"request_id": "diagnostic-01"}
    report["requests"].append(row)
    ai, _ = modules(
        lambda **kw: SimpleNamespace(text=json.dumps({"results": [provider_row()]}))
    )
    with s1e.capture_responses(ai, output, report, row):
        ai.embedding_client().models.generate_content()
        assert (
            row["provider_snapshots"][0]["results"][0]["intervals"][0]["end_seconds"]
            == 27.5
        )
        # A crash at the validator must not erase this numeric observation.
        saved = json.loads(output.read_text())
        assert saved["requests"][0]["provider_snapshots"] == row["provider_snapshots"]


def test_duplicate_request_and_paid_access_rejected_before_client_or_budget(tmp_path):
    ai = SimpleNamespace(embedding_client=lambda: pytest.fail("No client"))
    config = SimpleNamespace(VISUAL_TIER="unpaid", FPS=30)
    report = {"requests": [{"request_id": "one"}]}
    with pytest.raises(ValueError, match="already exists"):
        s1e.run_probe(
            frozen_case(),
            "one",
            "diagnostic",
            tmp_path / "ledger.json",
            report,
            ai,
            config,
            None,
            SimpleNamespace(),
        )
    config.VISUAL_TIER = "paid"
    with pytest.raises(ValueError, match="unpaid"):
        s1e.run_probe(
            frozen_case(),
            "two",
            "diagnostic",
            tmp_path / "ledger.json",
            report,
            ai,
            config,
            None,
            SimpleNamespace(),
        )
    assert not (tmp_path / "ledger.json").exists()


def diagnostic_reference(case):
    return {
        "request_id": "diagnostic-01",
        "purpose": "diagnostic",
        "case": case,
        "identity": {"model": "fixed-model"},
        "provider_snapshots": [
            s1e.safe_response(
                json.dumps({"results": [provider_row(21.333, "observed_stop")]})
            )
        ],
    }


def test_correction_has_independent_cache_key_and_restores_product_state():
    case = frozen_case()
    note = s1e.correction_note(
        case, {"requests": [diagnostic_reference(case)]}, "diagnostic-01", "fixed-model"
    )
    candidate = real_grounding.InspectionCandidate(
        "c0",
        Path(case["input"]),
        case["sha256"],
        *case["anchor"],
        case["asset_frames"],
        *case["context"],
    )
    before_version = real_grounding.CONTINUATION_VERSION
    before_key = real_grounding.continuation_cache_key(
        case["query"], candidate, case["activity"], case["direction"]
    )
    source_before = (ROOT / "server/grounding.py").read_bytes()
    ai, _ = modules(lambda **kw: None)
    original_client = ai.embedding_client
    with (
        pytest.raises(RuntimeError),
        s1e.correction_experiment(ai, real_grounding, note),
    ):
        correction_key = real_grounding.continuation_cache_key(
            case["query"], candidate, case["activity"], case["direction"]
        )
        assert correction_key != before_key
        assert real_grounding.CONTINUATION_VERSION == s1e.CORRECTION_VERSION
        raise RuntimeError("restore even when request fails")
    assert real_grounding.CONTINUATION_VERSION == before_version
    assert ai.embedding_client is original_client
    assert (ROOT / "server/grounding.py").read_bytes() == source_before


def test_one_off_correction_appends_only_review_prompt_and_uses_same_ledger(tmp_path):
    case = frozen_case()
    output = tmp_path / "ledger.json"
    report = {"requests": [diagnostic_reference(case)]}
    EvaluationBudget(output, report, 8, 180).reserve(27.5)
    sent = []

    def dispatch(**kwargs):
        sent.append(kwargs)
        saved = json.loads(output.read_text())
        assert saved["evaluation_budget"]["generation_attempts"] == 2
        assert (
            saved["requests"][-1]["experiment"]["reference_request_id"]
            == "diagnostic-01"
        )
        return SimpleNamespace(text=json.dumps({"results": [provider_row()]}))

    ai, grounding = modules(dispatch)
    grounding.CONTINUATION_VERSION = "unchanged-product-version"
    grounding.InspectionCandidate = real_grounding.InspectionCandidate
    grounding._validated_continuation = real_grounding._validated_continuation

    def inspect(query, spec, **kwargs):
        assert grounding.CONTINUATION_VERSION == s1e.CORRECTION_VERSION
        data = grounding.verification_clip(None, 75, 900)
        response = ai.embedding_client().models.generate_content(
            model="fixed-model", contents=["unchanged original prompt", part(data)]
        )
        verdict = real_grounding._validated_continuation(
            real_grounding.InspectionCandidate(*spec),
            json.loads(response.text)["results"][0],
            case["activity"],
            "after",
        )
        return {"c0": verdict}, None

    grounding.inspect_continuation = inspect
    config = SimpleNamespace(
        VISUAL_TIER="unpaid", FPS=30, VISUAL_VERIFIER_MODEL="fixed-model"
    )
    row = s1e.run_probe(
        case,
        "correction-01",
        "correction",
        output,
        report,
        ai,
        config,
        None,
        grounding,
        reference_request_id="diagnostic-01",
    )
    assert row["offline_validation"]["status"] == "accepted"
    assert report["evaluation_budget"]["generation_attempts"] == 2
    assert report["evaluation_budget"]["supplied_video_seconds"] == 55
    assert sent[0]["model"] == "fixed-model"
    assert sent[0]["contents"][0] == "unchanged original prompt"
    assert sent[0]["contents"][1].inline_data.data == b"75:900"
    suffix = sent[0]["contents"][-1]
    assert "LOCAL 21.333 seconds" in suffix
    assert "900" not in suffix and "27.5" not in suffix
    assert "ordinary pause" in suffix and "unverified hypothesis" in suffix
    assert "alleged handshake" in suffix and "did or did not occur" in suffix
    assert grounding.CONTINUATION_VERSION == "unchanged-product-version"
    with pytest.raises(ValueError, match="already been attempted"):
        s1e.run_probe(
            case,
            "correction-02",
            "correction",
            output,
            report,
            ai,
            config,
            None,
            grounding,
            reference_request_id="diagnostic-01",
        )
    assert len(sent) == 1


def test_correction_refuses_changed_model_or_video_context():
    case = frozen_case()
    report = {"requests": [diagnostic_reference(case)]}
    with pytest.raises(ValueError, match="diagnostic video"):
        s1e.correction_note(case, report, "diagnostic-01", "different-model")
    changed = {**case, "context": [60, 900]}
    with pytest.raises(ValueError, match="diagnostic video"):
        s1e.correction_note(changed, report, "diagnostic-01", "fixed-model")
