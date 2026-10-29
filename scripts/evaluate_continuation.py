"""Bounded paired development comparison; no calls without explicit consent.

Use the same videos, anchors, model and sampling for discovery versus continuation.
This measures a known activity's extension, not retrieval or independent accuracy.
"""

import argparse
import fcntl
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.evaluate_activity_search import (
    EvaluationBudget,
    EvaluationLimitReached,
    observe_dispatches,
    runtime_sources,
    save_report,
)


def load_cases(path, root):
    frozen_bytes = path.read_bytes()
    fixture = json.loads(frozen_bytes)
    if fixture.get("fps") != 30 or not fixture.get("frozen_before_live_comparison"):
        raise ValueError("Use a frozen 30fps continuation fixture")
    cases = fixture["cases"]
    if len(cases) != 4 or len({case["id"] for case in cases}) != 4:
        raise ValueError("The comparison requires four distinct frozen cases")
    for case in cases:
        path = (root / case["input"]).resolve()
        if not path.is_relative_to(root.resolve()):
            raise ValueError("Media must be inside the repository's local storage")
        if hashlib.sha256(path.read_bytes()).hexdigest() != case["sha256"]:
            raise ValueError(f"Source hash changed: {case['id']}")
        left, right = case["context"]
        a, b = case["anchor"]
        if not 0 <= left <= a < b <= right <= case["asset_frames"]:
            raise ValueError(f"Invalid frozen frame ranges: {case['id']}")
        if right - left > 900:
            raise ValueError("An inspection cannot exceed 30 seconds")
    return cases, hashlib.sha256(frozen_bytes).hexdigest()


def assess(case, verdict, error_code=None):
    """Compare semantic continuity separately from approximate boundary location."""
    if error_code:
        return {"status": "inspection_failed", "error_code": error_code}
    if not verdict or verdict.get("decision") != "match":
        return {"status": "no_matching_extension", "passed": False}
    left, right = case["anchor"]
    spans = [
        span
        for span in verdict.get("intervals", [])
        if max(left, span["start_frame"]) < min(right, span["end_frame"])
    ]
    if not spans:
        return {"status": "disconnected_occurrence", "passed": False}
    # Choosing the overlap is the previous worker's behavior. Extra disjoint
    # proposals are reported independently rather than hidden by a lucky first hit.
    span = max(
        spans, key=lambda s: min(right, s["end_frame"]) - max(left, s["start_frame"])
    )
    side = case["direction"]
    boundary_name = "start" if side == "before" else "end"
    low, high = case["expected"][boundary_name + "_frame_bounds"]
    boundary = span[boundary_name + "_frame"]
    unresolved = span.get("continues_" + side, False) or span.get(
        "boundary_conflict_" + side, False
    )
    temporal_pass = low <= boundary <= high and not unresolved
    semantic_pass = verdict.get("continuity") == "same_activity"
    return {
        "status": "evaluated",
        "boundary_frame": boundary,
        "expected_bounds": [low, high],
        "boundary_pass": temporal_pass,
        "semantic_continuity": verdict.get("continuity", "not_separately_tested"),
        "extra_occurrences": len(verdict.get("intervals", [])) - 1,
        "passed": temporal_pass and semantic_pass if "continuity" in verdict else None,
    }


def seed_baseline_cache(source, db, grounding, query, spec):
    """Copy only an exact contract key, not projects, usage or arbitrary results."""
    if source is None:
        return False
    key = grounding.cache_key(query, grounding.InspectionCandidate(*spec))
    with sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True) as conn:
        row = conn.execute("SELECT value FROM cache WHERE key=?", (key,)).fetchone()
    if row:
        db.cache_set(key, json.loads(row[0]))
    return bool(row)


def run_cases(
    cases, root, output, report, budget, ai, config, db, grounding, baseline_cache=None
):
    counts = report.setdefault(
        "dispatch_counts", {"embedding_requests": 0, "video_requests": 0}
    )
    completed = {(row["case_id"], row["variant"]) for row in report["comparisons"]}
    with observe_dispatches(ai, grounding, budget, counts, config.FPS):
        for case in cases:
            spec = (
                "c0",
                root / case["input"],
                case["sha256"],
                *case["anchor"],
                case["asset_frames"],
                *case["context"],
            )
            for variant in ("general_discovery", "anchored_continuation"):
                if (case["id"], variant) in completed:
                    continue
                row = {"case_id": case["id"], "variant": variant, "status": "started"}
                report["comparisons"].append(row)
                save_report(output, report)
                diagnostics = {}
                try:
                    if variant == "general_discovery":
                        row["exact_baseline_cache_found"] = seed_baseline_cache(
                            baseline_cache, db, grounding, case["query"], spec
                        )
                        results, error = grounding.inspect_ranges(
                            case["query"], [spec], diagnostics=diagnostics
                        )
                    else:
                        results, error = grounding.inspect_continuation(
                            case["query"],
                            spec,
                            established_activity=case["activity"],
                            direction=case["direction"],
                            diagnostics=diagnostics,
                        )
                    verdict = results.get("c0")
                    code = getattr(error, "inspection_code", None) if error else None
                    row.update(
                        status="finished",
                        verdict=verdict,
                        assessment=assess(case, verdict, code),
                    )
                except EvaluationLimitReached:
                    row.update(status="budget_stopped")
                    return
                except BaseException as exc:
                    row.update(status="interrupted", error_type=type(exc).__name__)
                    raise
                finally:
                    row["diagnostics"] = diagnostics
                    report["dispatch_counts"] = counts
                    save_report(output, report)
                if budget.stopped:
                    return


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixture",
        type=Path,
        default=root / "tests/fixtures/continuation-cases-v1.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "data/evaluation/gemini-fresh/continuation-comparison-v1.json",
    )
    parser.add_argument("--baseline-cache", type=Path)
    parser.add_argument("--allow-free-gemini", action="store_true")
    parser.add_argument(
        "--playback-reviewed",
        action="store_true",
        help="Confirm actual playback review of all four frozen contexts",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-generation-attempts", type=int, default=8)
    parser.add_argument("--max-video-seconds", type=float, default=240)
    args = parser.parse_args()
    if (
        not 0 <= args.max_generation_attempts <= 8
        or not 0 <= args.max_video_seconds <= 240
    ):
        parser.error(
            "This ticket is capped at eight attempts and 240 supplied video seconds"
        )
    cases, frozen_hash = load_cases(args.fixture, root)
    if args.dry_run:
        print(
            json.dumps(
                {
                    "case_ids": [case["id"] for case in cases],
                    "frozen_sha256": frozen_hash,
                    "unretried_paired_video_seconds": sum(
                        (c["context"][1] - c["context"][0]) / 30 * 2 for c in cases
                    ),
                },
                indent=2,
            )
        )
        return
    if not args.allow_free_gemini or not args.playback_reviewed:
        parser.error("Both --allow-free-gemini and --playback-reviewed are required")
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    os.environ["STORYROOM_DATA"] = str(output.parent / (output.stem + "-cache"))
    from server import ai, config, db, grounding

    if config.VISUAL_TIER != "unpaid" or not config.visual_ai_ready():
        parser.error("Only configured unpaid Gemini access is permitted")
    identity = {
        "study": "continuation-development-v1",
        "frozen_sha256": frozen_hash,
        "code_revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip(),
        "runtime_sources": {
            **runtime_sources(root),
            "scripts/evaluate_continuation.py": hashlib.sha256(
                Path(__file__).read_bytes()
            ).hexdigest(),
        },
        "baseline_contract": grounding.VERSION,
        "continuation_contract": grounding.CONTINUATION_VERSION,
        "model": config.VISUAL_VERIFIER_MODEL,
        "sample_fps": 3,
        "playback_reviewed": True,
        "data_dir": str(config.DATA),
    }
    with output.with_suffix(output.suffix + ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        report = {**identity, "comparisons": []}
        if output.exists():
            report = json.loads(output.read_text())
            if any(report.get(key) != value for key, value in identity.items()):
                parser.error(
                    "Comparison identity changed; do not overwrite historical evidence"
                )
        budget = EvaluationBudget(
            output, report, args.max_generation_attempts, args.max_video_seconds
        )
        db.init()
        run_cases(
            cases,
            root,
            output,
            report,
            budget,
            ai,
            config,
            db,
            grounding,
            args.baseline_cache,
        )
    print(
        json.dumps(
            {
                "output": str(output),
                "budget": report["evaluation_budget"],
                "stop": report.get("evaluation_stop"),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
