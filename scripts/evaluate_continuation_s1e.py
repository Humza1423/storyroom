"""One authorized S1e probe at a time; shared durable 8-attempt/180-second cap.

Provider response text never enters the ledger. Numeric/enum snapshots support
offline validation replay, not replay of the model's semantic judgment.
"""

import argparse
import fcntl
import hashlib
import json
import math
import os
import re
import subprocess
import sys
from contextlib import contextmanager, nullcontext
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.evaluate_activity_search import (
    EvaluationBudget,
    EvaluationLimitReached,
    runtime_sources,
    save_report,
)

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "data/evaluation/gemini-fresh/s1e-ledger.json"
CORRECTION_VERSION = "s1e-one-off-trailing-court-review-v1-3fps"
ENUMS = {
    "intent": ("broad_activity", "specific_move"),
    "decision": ("match", "no_match", "uncertain"),
    "continuity": ("same_activity", "different_activity", "uncertain"),
    "boundary_outcome": ("continues", "observed_stop", "uncertain"),
}
NUMBERS = (
    "start_seconds",
    "end_seconds",
    "suggested_start_seconds",
    "suggested_end_seconds",
    "start_frame",
    "end_frame",
    "suggested_start_frame",
    "suggested_end_frame",
    "requested_duration_seconds",
)
FLAGS = (
    "continues_before",
    "continues_after",
    "boundary_conflict_before",
    "boundary_conflict_after",
)


def correction_note(case, report, reference_id, model):
    """Freeze one specific response review, not a target boundary or prompt loop."""
    if any(row.get("purpose") == "correction" for row in report["requests"]):
        raise ValueError("The one-off correction has already been attempted")
    references = [
        row for row in report["requests"] if row["request_id"] == reference_id
    ]
    if len(references) != 1 or references[0].get("purpose") != "diagnostic":
        raise ValueError("Correction requires one saved diagnostic request")
    reference = references[0]
    same_fields = (
        "query",
        "sha256",
        "context",
        "anchor",
        "asset_frames",
        "activity",
        "direction",
    )
    if (
        any(reference["case"].get(key) != case.get(key) for key in same_fields)
        or reference.get("identity", {}).get("model") != model
    ):
        raise ValueError(
            "Correction must use the diagnostic video, context, interpretation and model"
        )
    if case["direction"] != "after" or case["activity"]["intent"] != "broad_activity":
        raise ValueError(
            "This one-off experiment only reviews a trailing broad-activity stop"
        )
    snapshots = reference.get("provider_snapshots", [])
    rows = snapshots[-1].get("results", []) if snapshots else []
    if (
        len(rows) != 1
        or not rows[0].get("candidate_id_matches")
        or rows[0].get("boundary_outcome") != "observed_stop"
        or len(rows[0].get("intervals", [])) != 1
    ):
        raise ValueError("Diagnostic lacks one observed-stop interval to review")
    previous_end = rows[0]["intervals"][0].get("end_seconds")
    if not numeric(previous_end):
        raise ValueError("Diagnostic stop must be a finite supplied-video timestamp")
    return (
        "S1e ONE-OFF BOUNDARY REVIEW. A previous inspection proposed an observed stop at "
        f"LOCAL {previous_end:g} seconds. Treat that endpoint as an unverified hypothesis, not ground truth. "
        "Its explanation also alleged that the players gather and shake hands near that timestamp. "
        "Re-inspect that specific alleged handshake and stop; do not assume that it did or did not occur. "
        "Inspect the footage immediately before and after that timestamp and the remaining supplied footage. "
        "For this broad badminton-court activity, distinguish an individual rally ending or an ordinary pause "
        "between exchanges from the established court activity actually ending. Check whether the same "
        "players and court activity visibly persist or resume across the pause, or whether a distinct activity "
        "or genuinely separate occurrence begins. A pause alone is not an observed stop; shared scenery alone "
        "does not establish continuity. Do not join unrelated actions or separate occurrences. Return one "
        "connected interval supported by the video and covering the marked overlap, with concrete continuity "
        "evidence and the appropriate boundary outcome. Do not aim for any expected endpoint or desired edit "
        "length. If the trailing extent cannot be established, return uncertain rather than guessing."
    )


@contextmanager
def correction_experiment(ai, grounding, note):
    """Process-local prompt/cache change; product source and old cache stay intact."""
    original_client, original_version = (
        ai.embedding_client,
        grounding.CONTINUATION_VERSION,
    )

    def client():
        api = original_client()
        generate = api.models.generate_content

        def observed(**kwargs):
            kwargs = {**kwargs, "contents": [*kwargs.get("contents", []), note]}
            return generate(**kwargs)

        return SimpleNamespace(
            models=SimpleNamespace(
                generate_content=observed, embed_content=api.models.embed_content
            ),
            close=api.close,
        )

    grounding.CONTINUATION_VERSION, ai.embedding_client = CORRECTION_VERSION, client
    try:
        yield
    finally:
        grounding.CONTINUATION_VERSION, ai.embedding_client = (
            original_version,
            original_client,
        )


@contextmanager
def bounded_dispatches(ai, grounding, budget, counts, fps):
    """Reserve before every SDK entry; forward endpoint sampling arguments."""
    original_client, original_clip = ai.embedding_client, grounding.verification_clip
    durations = {}

    def clip(proxy, start, end, **kwargs):
        video = original_clip(proxy, start, end, **kwargs)
        digest = hashlib.sha256(video).digest()
        durations[digest] = max(durations.get(digest, 0), (end - start) / fps)
        return video

    def seconds(contents):
        total = 0
        for part in contents:
            if isinstance(part, str):
                continue
            nested = getattr(part, "parts", None)
            if nested is not None:
                total += seconds(nested)
                continue
            blob = getattr(part, "inline_data", None)
            if blob and str(getattr(blob, "mime_type", "")).startswith("video/"):
                digest = hashlib.sha256(blob.data).digest()
                if digest not in durations:
                    raise ValueError("Unaccounted video; S1e dispatch refused")
                total += durations[digest]
            elif (
                getattr(part, "file_data", None)
                or blob
                or not isinstance(getattr(part, "text", None), str)
            ):
                raise ValueError("Unaccounted content; S1e dispatch refused")
        return total

    def client():
        api = original_client()
        generate = api.models.generate_content

        def observed(**kwargs):
            budget.reserve(seconds(kwargs.get("contents", [])))
            counts["video_requests"] += 1
            return generate(**kwargs)

        def no_embeddings(**kwargs):
            raise ValueError("S1e continuation probes do not require embeddings")

        return SimpleNamespace(
            models=SimpleNamespace(
                generate_content=observed, embed_content=no_embeddings
            ),
            close=api.close,
        )

    grounding.verification_clip, ai.embedding_client = clip, client
    try:
        yield
    finally:
        grounding.verification_clip, ai.embedding_client = (
            original_clip,
            original_client,
        )


def numeric(value):
    return type(value) in (int, float) and math.isfinite(value)


def safe_value(value):
    """Keep bounded structured observations, never arbitrary model-written text."""
    if not isinstance(value, dict):
        return {"malformed": True}
    result = {key: value[key] for key in NUMBERS if numeric(value.get(key))}
    result.update({key: value[key] for key in FLAGS if type(value.get(key)) is bool})
    result.update(
        {key: value[key] for key, allowed in ENUMS.items() if value.get(key) in allowed}
    )
    for key in ("visible_evidence", "continuity_evidence"):
        evidence = value.get(key)
        result[key + "_present"] = isinstance(evidence, str) and bool(evidence.strip())
        result[key + "_length"] = (
            min(len(evidence), 100_000) if isinstance(evidence, str) else 0
        )
    intervals = value.get("intervals")
    if isinstance(intervals, list):
        result["interval_count"] = len(intervals)
        result["intervals"] = [safe_value(item) for item in intervals[:2]]
    return result


def safe_response(text):
    if not isinstance(text, str) or len(text) > 1_000_000:
        return {"malformed": True}
    try:
        parsed = json.loads(text)
    except (ValueError, TypeError):
        return {"malformed": True}
    rows = parsed.get("results") if isinstance(parsed, dict) else None
    if not isinstance(rows, list):
        return {"malformed": True}
    return {
        "row_count": len(rows),
        "results": [
            {
                **safe_value(row),
                "candidate_id_matches": isinstance(row, dict)
                and row.get("candidate_id") == "c0",
            }
            for row in rows[:5]
        ],
    }


def restore_for_validation(value):
    """Evidence placeholders retain shape/length checks, not semantic content."""
    result = {key: value[key] for key in (*NUMBERS, *FLAGS, *ENUMS) if key in value}
    for key in ("visible_evidence", "continuity_evidence"):
        length = value.get(key + "_length", 0)
        result[key] = "x" * min(length, 2001) if value.get(key + "_present") else ""
    if "interval_count" in value:
        result["intervals"] = [
            restore_for_validation(item) for item in value.get("intervals", [])
        ]
        # More than two intervals must remain invalid without retaining unbounded data.
        if value["interval_count"] > 2:
            result["intervals"].append({})
    return result


@contextmanager
def capture_responses(ai, output, report, row):
    original = ai.embedding_client

    def client():
        api = original()
        generate = api.models.generate_content

        def observed(**kwargs):
            response = generate(**kwargs)
            row.setdefault("provider_snapshots", []).append(
                safe_response(getattr(response, "text", None))
            )
            save_report(output, report)
            return response

        return SimpleNamespace(
            models=SimpleNamespace(
                generate_content=observed, embed_content=api.models.embed_content
            ),
            close=api.close,
        )

    ai.embedding_client = client
    try:
        yield
    finally:
        ai.embedding_client = original


def load_case(fixture_path, case_id, expected_hash, root=ROOT):
    raw = fixture_path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected_hash:
        raise ValueError("Supplementary label hash changed; refreeze before dispatch")
    fixture = json.loads(raw)
    if not fixture.get("frozen_before_live_comparison") or fixture.get("fps") != 30:
        raise ValueError("A frozen 30fps supplementary label file is required")
    matching = [case for case in fixture["cases"] if case["id"] == case_id]
    if len(matching) != 1:
        raise ValueError("Choose exactly one frozen case")
    case = matching[0]
    path = (root / case["input"]).resolve()
    if (
        not path.is_relative_to(root.resolve())
        or hashlib.sha256(path.read_bytes()).hexdigest() != case["sha256"]
    ):
        raise ValueError("Source identity changed")
    left, right = case["context"]
    a, b = case["anchor"]
    if (
        not all(type(v) is int for v in (left, right, a, b, case["asset_frames"]))
        or not 0 <= left <= a < b <= right <= case["asset_frames"]
        or right - left > 900
    ):
        raise ValueError("Invalid bounded frame ranges")
    return case, digest


def replay(row, grounding):
    """Offline numeric/enum validation only. No provider/client invocation."""
    case = row["case"]
    snapshots = row.get("provider_snapshots", [])
    if not snapshots:
        return {"status": "no_provider_response", "semantic_revalidation": False}
    snapshot = snapshots[-1]
    rows = snapshot.get("results", [])
    matches = [value for value in rows if value.get("candidate_id_matches")]
    if snapshot.get("row_count") != 1 or len(matches) != 1:
        return {
            "status": "rejected",
            "error_code": "candidate_set_invalid",
            "semantic_revalidation": False,
        }
    spec = grounding.InspectionCandidate(
        "c0",
        Path(case["input"]),
        case["sha256"],
        *case["anchor"],
        case["asset_frames"],
        *case["context"],
    )
    value = restore_for_validation(matches[0])
    if row.get("purpose") == "endpoint":
        return {
            "status": "endpoint_replay_not_implemented",
            "semantic_revalidation": False,
        }
    validator = grounding._validated_continuation
    try:
        result = validator(spec, value, case["activity"], case["direction"])
        return {
            "status": "accepted",
            "normalized": safe_value(result),
            "semantic_revalidation": False,
        }
    except (ValueError, TypeError) as exc:
        return {
            "status": "rejected",
            "error_code": getattr(exc, "inspection_code", "validation_failed"),
            "reason": getattr(exc, "reason", None),
            "semantic_revalidation": False,
        }


def run_probe(
    case,
    request_id,
    purpose,
    output,
    report,
    ai,
    config,
    db,
    grounding,
    identity=None,
    reference_request_id=None,
):
    if config.VISUAL_TIER != "unpaid":
        raise ValueError("S1e permits unpaid Gemini access only")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", request_id):
        raise ValueError("Request ID must be a short opaque identifier")
    if any(row["request_id"] == request_id for row in report["requests"]):
        raise ValueError(
            "Request ID already exists; an explicit new ID is required for another call"
        )
    function = grounding.inspect_continuation
    note = (
        correction_note(
            case, report, reference_request_id, config.VISUAL_VERIFIER_MODEL
        )
        if purpose == "correction"
        else None
    )
    if purpose == "endpoint":
        function = getattr(grounding, "inspect_endpoint", None)
        if function is None:
            raise ValueError(
                "Endpoint method is not implemented; no dispatch permitted"
            )
    budget = EvaluationBudget(output, report, 8, 180)
    row = {
        "request_id": request_id,
        "purpose": purpose,
        "case": case,
        "status": "started",
        "identity": identity or {},
    }
    if note:
        row["experiment"] = {
            "version": CORRECTION_VERSION,
            "reference_request_id": reference_request_id,
            "prompt_suffix": note,
            "prompt_suffix_sha256": hashlib.sha256(note.encode()).hexdigest(),
        }
    report["requests"].append(row)
    save_report(output, report)
    counts = report.setdefault(
        "dispatch_counts", {"embedding_requests": 0, "video_requests": 0}
    )
    spec = (
        "c0",
        ROOT / case["input"],
        case["sha256"],
        *case["anchor"],
        case["asset_frames"],
        *case["context"],
    )
    diagnostics = {}
    try:
        with (
            correction_experiment(ai, grounding, note) if note else nullcontext(),
            bounded_dispatches(ai, grounding, budget, counts, config.FPS),
            capture_responses(ai, output, report, row),
        ):
            endpoint = (
                {"provisional_boundary_frame": case["provisional_boundary_frame"]}
                if purpose == "endpoint"
                else {}
            )
            results, error = function(
                case["query"],
                spec,
                established_activity=case["activity"],
                direction=case["direction"],
                diagnostics=diagnostics,
                **endpoint,
            )
        row.update(
            status="finished",
            normalized=safe_value(results.get("c0")),
            error_code=getattr(error, "inspection_code", None) if error else None,
        )
    except EvaluationLimitReached:
        row.update(status="budget_stopped")
        return row
    except BaseException as exc:
        row.update(status="interrupted", error_type=type(exc).__name__)
        raise
    finally:
        # Product diagnostics contain fixed safe categories; no provider message.
        row["diagnostics"] = diagnostics
        if budget.stopped:
            row["status"] = "budget_stopped"
        save_report(output, report)
    row["offline_validation"] = replay(row, grounding)
    save_report(output, report)
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-file", type=Path)
    parser.add_argument("--case-id")
    parser.add_argument("--expected-fixture-sha256")
    parser.add_argument("--request-id")
    parser.add_argument(
        "--reference-request-id",
        help="For the one-off correction, identify its saved diagnostic",
    )
    parser.add_argument(
        "--purpose",
        choices=("diagnostic", "correction", "endpoint"),
        default="diagnostic",
    )
    parser.add_argument("--allow-free-gemini", action="store_true")
    parser.add_argument("--playback-reviewed", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--replay", metavar="REQUEST_ID")
    args = parser.parse_args()
    if args.replay:
        report = json.loads(LEDGER.read_text())
        matches = [
            row for row in report["requests"] if row["request_id"] == args.replay
        ]
        if len(matches) != 1:
            parser.error("Unknown saved request ID")
        from server import grounding

        print(json.dumps(replay(matches[0], grounding), indent=2))
        return
    if not all(
        (args.case_file, args.case_id, args.expected_fixture_sha256, args.request_id)
    ):
        parser.error(
            "Case file, case ID, expected fixture hash and unique request ID are required"
        )
    if args.purpose == "correction" and not args.reference_request_id:
        parser.error("Correction requires --reference-request-id")
    case, frozen_hash = load_case(
        args.case_file, args.case_id, args.expected_fixture_sha256
    )
    if args.dry_run:
        print(
            json.dumps(
                {
                    "case_id": case["id"],
                    "fixture_sha256": frozen_hash,
                    "video_seconds_per_attempt": (
                        case["context"][1] - case["context"][0]
                    )
                    / 30,
                    "ledger": str(LEDGER),
                    "limit": {"attempts": 8, "video_seconds": 180},
                },
                indent=2,
            )
        )
        return
    if not args.allow_free_gemini or not args.playback_reviewed:
        parser.error("Explicit unpaid access and actual playback review are required")
    os.environ["STORYROOM_DATA"] = str(LEDGER.parent / "s1e-cache")
    from server import ai, config, db, grounding

    if config.VISUAL_TIER != "unpaid" or not config.visual_ai_ready():
        parser.error("Configure acknowledged unpaid Gemini access; no paid fallback")
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        report = (
            json.loads(LEDGER.read_text())
            if LEDGER.exists()
            else {"study": "continuation-s1e", "requests": []}
        )
        if report.get("study") != "continuation-s1e":
            parser.error("Existing ledger belongs to another study")
        identity = {
            "fixture_sha256": frozen_hash,
            "model": config.VISUAL_VERIFIER_MODEL,
            "continuation_contract": grounding.CONTINUATION_VERSION,
            "code_revision": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip(),
            "runtime_sources": {
                **runtime_sources(ROOT),
                "scripts/evaluate_continuation_s1e.py": hashlib.sha256(
                    Path(__file__).read_bytes()
                ).hexdigest(),
            },
        }
        # Identity is per request: a correction uses the same cumulative budget.
        db.init()
        row = run_probe(
            case,
            args.request_id,
            args.purpose,
            LEDGER,
            report,
            ai,
            config,
            db,
            grounding,
            identity,
            args.reference_request_id,
        )
        save_report(LEDGER, report)
    print(
        json.dumps(
            {
                "request_id": args.request_id,
                "status": row["status"],
                "offline_validation": row.get("offline_validation"),
                "budget": report["evaluation_budget"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
