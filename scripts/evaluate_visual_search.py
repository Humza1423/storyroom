"""Run human-judged visual retrieval evaluation against an isolated Storyroom DB.

The dataset JSON contains query labels, not filenames used by the model. The
runner refuses the normal project data directory. Missing query vectors and
video verdicts are cache-only by default; --allow-free-gemini explicitly
permits unpaid-tier calls for both on the isolated data directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import sys
import time
from pathlib import Path


def interval_iou(left, right):
    intersection = max(0.0, min(left[1], right[1]) - max(left[0], right[0]))
    union = max(left[1], right[1]) - min(left[0], right[0])
    return intersection / union if union > 0 else 0.0


def candidate_matches(candidate, expected, fps=30, min_iou=0.25):
    """Match one result to a manually labeled asset/time interval."""
    if candidate["asset_id"] != expected["asset_id"]:
        return False
    actual = (candidate["start_frame"] / fps, candidate["end_frame"] / fps)
    target = (float(expected["start_sec"]), float(expected["end_sec"]))
    # Midpoint containment is insufficient: a whole-file result can contain a
    # correct action while including many unrelated actions around it.
    return interval_iou(actual, target) >= min_iou


def classify_miss(row, returned, trace, fps_by_asset):
    """Locate the earliest stage at which a labeled positive was lost."""
    expected = row.get("relevant", [])
    if row.get("kind") == "negative":
        return "false_positive" if returned else "correct_rejection"
    if any(
        candidate_matches(hit, target, fps_by_asset.get(hit.get("asset_id"), 30))
        for hit in returned for target in expected
    ):
        return "success"
    ranked = trace.get("ranked_events", [])
    shortlist = trace.get("shortlist", [])
    if not any(hit.get("asset_id") == target["asset_id"]
               for hit in ranked for target in expected):
        return "retrieval_miss"
    if not any(candidate_matches(hit, target, fps_by_asset.get(hit.get("asset_id"), 30))
               for hit in ranked for target in expected):
        return "temporal_candidate_miss"
    if not any(candidate_matches(hit, target, fps_by_asset.get(hit.get("asset_id"), 30))
               for hit in shortlist for target in expected):
        return "shortlist_miss"
    if trace.get("verifier_error"):
        return "verifier_error"
    if not any(hit.get("accepted") and candidate_matches(
        hit, target, fps_by_asset.get(hit.get("asset_id"), 30)
    ) for hit in trace.get("verifier", []) for target in expected):
        return "verifier_rejection"
    return "boundary_miss"


def evaluate_rows(rows, returned_by_id, fps_by_asset=None, diagnose_stages=True):
    """Score source retrieval, event localization, negatives, and boundaries separately."""
    fps_by_asset = fps_by_asset or {}
    outcomes = []
    boundary_errors = []
    for row in rows:
        returned = returned_by_id[row["id"]]
        expected = row.get("relevant", [])
        trace = row.get("trace", {})
        if row.get("kind") == "negative":
            outcomes.append(
                {
                    "id": row["id"],
                    "category": row["category"],
                    "split": row["split"],
                    "kind": "negative",
                    "top5_hit": not bool(returned),
                    "top1_relevant": False,
                    "returned_any": bool(returned),
                    "boundary_error_sec": None,
                    "asset_top5_hit": False,
                    "failure_stage": classify_miss(row, returned, trace, fps_by_asset)
                    if diagnose_stages else "not_applicable",
                    "latency_ms": trace.get("latency_ms"),
                }
            )
            continue
        matches = [
            any(candidate_matches(hit, target, fps_by_asset.get(hit["asset_id"], 30))
                for target in expected)
            for hit in returned
        ]
        asset_top5 = any(hit.get("asset_id") == target["asset_id"]
                         for hit in returned for target in expected)
        top5 = any(matches)
        top1 = bool(matches and matches[0])
        matched_target = next(
            (
                target
                for hit, is_match in zip(returned, matches)
                if is_match
                for target in expected
                if candidate_matches(hit, target, fps_by_asset.get(hit["asset_id"], 30))
            ),
            None,
        )
        boundary_error = None
        if matched_target:
            matched_hit = next(
                hit
                for hit in returned
                if candidate_matches(hit, matched_target,
                                     fps_by_asset.get(hit["asset_id"], 30))
            )
            fps = fps_by_asset.get(matched_hit["asset_id"], 30)
            start_error = abs(
                matched_hit["start_frame"] / fps - float(matched_target["start_sec"])
            )
            end_error = abs(
                matched_hit["end_frame"] / fps - float(matched_target["end_sec"])
            )
            boundary_error = max(start_error, end_error)
            boundary_errors.append(boundary_error)
        outcomes.append(
            {
                "id": row["id"],
                "category": row["category"],
                "split": row["split"],
                "kind": row["kind"],
                "top5_hit": top5,
                "top1_relevant": top1,
                "returned_any": bool(returned),
                "boundary_error_sec": boundary_error,
                "asset_top5_hit": asset_top5,
                "failure_stage": classify_miss(row, returned, trace, fps_by_asset)
                if diagnose_stages else "not_applicable",
                "latency_ms": trace.get("latency_ms"),
            }
        )

    def rate(items, predicate):
        return sum(bool(predicate(item)) for item in items) / len(items) if items else None

    def summarize_group(group):
        positives = [row for row in group if row["kind"] != "negative"]
        negatives = [row for row in group if row["kind"] == "negative"]
        returned_queries = [row for row in group if row["returned_any"]]
        return {
            "queries": len(group),
            "positive_asset_top5_recall": rate(positives, lambda item: item["asset_top5_hit"]),
            "positive_top5_recall": rate(positives, lambda item: item["top5_hit"]),
            "positive_top1_accuracy": rate(positives, lambda item: item["top1_relevant"]),
            "top1_precision_on_returned": rate(
                returned_queries, lambda item: item["top1_relevant"]
            ),
            "negative_false_positive_rate": rate(
                negatives, lambda item: not item["top5_hit"]
            ),
        }
    by_category = {
        category: summarize_group([row for row in outcomes if row["category"] == category])
        for category in sorted({row["category"] for row in outcomes})
    }
    by_split = {
        split: summarize_group([row for row in outcomes if row["split"] == split])
        for split in sorted({row["split"] for row in outcomes})
    }
    return {
        "query_count": len(outcomes),
        "positive_asset_top5_recall": rate(
            [item for item in outcomes if item["kind"] != "negative"],
            lambda item: item["asset_top5_hit"],
        ),
        "positive_top5_recall": rate(
            [item for item in outcomes if item["kind"] != "negative"],
            lambda item: item["top5_hit"],
        ),
        "positive_top1_accuracy": rate(
            [item for item in outcomes if item["kind"] != "negative"],
            lambda item: item["top1_relevant"],
        ),
        "top1_precision_on_returned": rate(
            [item for item in outcomes if item["returned_any"]],
            lambda item: item["top1_relevant"],
        ),
        "negative_false_positive_rate": rate(
            [item for item in outcomes if item["kind"] == "negative"],
            lambda item: not item["top5_hit"],
        ),
        "median_boundary_error_sec": (
            statistics.median(boundary_errors) if boundary_errors else None
        ),
        "boundary_label_count": len(boundary_errors),
        "failure_stage_counts": {
            stage: sum(item["failure_stage"] == stage for item in outcomes)
            for stage in sorted({item["failure_stage"] for item in outcomes})
        },
        "latency_ms": {
            "p50": statistics.median(samples) if (samples := [
                item["latency_ms"] for item in outcomes if item["latency_ms"] is not None
            ]) else None,
            "p95": sorted(samples)[min(len(samples) - 1, int(len(samples) * 0.95))]
            if samples else None,
        },
        "by_category": by_category,
        "by_split": by_split,
        "per_query": outcomes,
    }


def validate_dataset(dataset, profile="full"):
    videos = dataset.get("videos")
    queries = dataset.get("queries")
    if not isinstance(videos, list) or not isinstance(queries, list):
        raise TypeError("Dataset must contain 'videos' and 'queries' arrays.")
    shapes = {
        "full": (50, 100, 5, 10, {"positive": 50, "paraphrase": 25, "negative": 25}),
        "pilot": (16, 60, 4, 4, {"positive": 36, "paraphrase": 12, "negative": 12}),
    }
    if profile not in shapes:
        raise ValueError(f"Unknown evaluation profile: {profile}")
    video_count, query_count, category_count, per_category, required_kinds = shapes[profile]
    if len(videos) != video_count:
        raise ValueError(f"Expected exactly {video_count} videos; found {len(videos)}.")
    if len(queries) != query_count:
        raise ValueError(f"Expected exactly {query_count} reviewed searches; found {len(queries)}.")
    categories = {video.get("category") for video in videos}
    if len(categories) != category_count:
        raise ValueError(f"Videos must cover exactly {category_count} footage categories.")
    category_counts = {
        category: sum(video.get("category") == category for video in videos)
        for category in categories
    }
    if any(count != per_category for count in category_counts.values()):
        raise ValueError(f"Use {per_category} videos in each footage category.")
    video_ids = [video.get("asset_id") for video in videos]
    if len(set(video_ids)) != len(video_ids) or None in video_ids:
        raise ValueError("Each video needs a unique indexed asset_id.")
    for video in videos:
        fps = float(video.get("normalized_fps", 30))
        if fps <= 0 or fps > 240:
            raise ValueError(f"Invalid normalized frame rate for {video['asset_id']}.")
    query_ids = [row.get("id") for row in queries]
    if len(set(query_ids)) != len(query_ids) or None in query_ids:
        raise ValueError("Each query must have a unique non-empty id.")
    for row in queries:
        if not row.get("project_id") or not row.get("query") or not row.get("category"):
            raise ValueError(f"Query {row.get('id')} needs project_id, query, and category.")
        if row.get("split") not in {"development", "test"}:
            raise ValueError(f"Query {row['id']} needs a development/test split.")
        if row.get("kind") not in {"positive", "paraphrase", "negative"}:
            raise ValueError(f"Invalid query kind in {row.get('id')}.")
        if row.get("kind") == "negative":
            if row.get("relevant"):
                raise ValueError(f"Negative query {row['id']} cannot have relevant ranges.")
        elif not row.get("relevant"):
            raise ValueError(f"Positive query {row['id']} needs labeled ranges.")
        for target in row.get("relevant", []):
            if target.get("asset_id") not in video_ids:
                raise ValueError(f"Query {row['id']} references an asset outside the benchmark.")
            if float(target.get("end_sec", 0)) <= float(target.get("start_sec", 0)):
                raise ValueError(f"Query {row['id']} has an invalid labeled range.")
    counts = {kind: sum(row["kind"] == kind for row in queries)
              for kind in ("positive", "paraphrase", "negative")}
    if counts != required_kinds:
        raise ValueError(f"Expected {required_kinds}; got {counts}.")
    return dataset


def validate_isolated_data_dir(data_dir: Path, repo: Path) -> Path:
    """Accept a dedicated benchmark DB, including one under ignored evaluation data."""
    resolved = data_dir.resolve()
    normal_data = (repo.resolve() / "data").resolve()
    # An isolated evaluation database may live below data/evaluation. Refuse
    # the live default directory itself and any broader directory that would
    # contain it (for example the repository root), but do not reject a
    # dedicated child database merely because it shares the ignored data tree.
    if resolved == normal_data or resolved in normal_data.parents:
        raise ValueError("Refusing to evaluate against the normal Storyroom data directory.")
    if not (resolved / "storyroom.sqlite").is_file():
        raise ValueError("The isolated data directory needs its own storyroom.sqlite.")
    return resolved


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path, help="Human-reviewed benchmark JSON")
    parser.add_argument(
        "--profile", choices=("full", "pilot"), default="full",
        help="Strict 50-video/100-query study or strict 16-video/60-query pilot",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        required=True,
        help="Dedicated isolated Storyroom data directory containing its indexed projects",
    )
    parser.add_argument(
        "--allow-free-gemini",
        action="store_true",
        help="Allow missing query vectors and video verdicts on Gemini's unpaid tier",
    )
    return parser.parse_args()


def install_instrumentation(ai, search_module, db, config, traces, allow_free_gemini):
    """Observe production's *batched* verifier without changing search decisions.

    Cache checks happen before either provider boundary. A cache-only evaluation
    therefore cannot accidentally issue a request when just one verdict in a
    five-candidate batch is missing.
    """
    from server.vector_index import ExactVectorIndex, filter_visual_candidates

    original_embedding_provider = ai.embedding_provider
    original_verify_batch = ai.verify_visual_matches
    original_rank = search_module.rank_distinct_events

    class CacheGuardProvider:
        def __init__(self, provider):
            self.provider = provider
            self.provider_name = provider.provider
            self.model = provider.model

        def __getattr__(self, name):
            return getattr(self.provider, name)

        def embed_text_query(self, query, job_id=None):
            prepared = f"task: search result | query: {query.strip()}"
            cache_key = (
                f"{self.provider_name}:{self.model}:{config.EMBED_DIMENSIONS}:query:{prepared}"
            )
            key = "visual-embedding:" + hashlib.sha256(cache_key.encode()).hexdigest()
            cached = db.cache_get(key)
            trace = traces.setdefault("current", {})
            trace["query_embedding_cache_hits"] = int(cached is not None)
            trace["query_embedding_request_attempts"] = int(cached is None and allow_free_gemini)
            if cached is not None:
                return cached
            if not allow_free_gemini:
                raise RuntimeError(f"Query vector is not cached for {query!r}; refusing a network call.")
            started = time.perf_counter()
            try:
                return self.provider.embed_text_query(query, job_id)
            finally:
                trace["query_embedding_ms"] = (time.perf_counter() - started) * 1000

    def guarded_verify_batch(query, candidates):
        trace = traces.setdefault("current", {})
        verifier = []
        missing = []
        for candidate_id, proxy, proxy_hash, start, end in candidates:
            cached = db.cache_get(ai.visual_verifier_cache_key(query, proxy_hash, start, end))
            item = {
                "candidate_id": candidate_id,
                "asset_id": proxy.parent.name,
                "start_frame": start,
                "end_frame": end,
                "cache_hit": cached is not None,
            }
            verifier.append(item)
            if cached is None:
                missing.append(item)
        trace["shortlist"] = [
            {key: item[key] for key in ("candidate_id", "asset_id", "start_frame", "end_frame")}
            for item in verifier
        ]
        trace["verifier_cache_hits"] = len(candidates) - len(missing)
        trace["verifier_cache_misses"] = len(missing)
        trace["verifier_batch_invocations"] = 1
        trace["verifier_request_attempts"] = int(bool(missing) and allow_free_gemini)
        if missing and not allow_free_gemini:
            absent = ", ".join(item["candidate_id"] for item in missing)
            raise RuntimeError(
                f"Visual verdict cache misses for {query!r} ({absent}); refusing a network call."
            )
        started = time.perf_counter()
        try:
            verdicts, error = original_verify_batch(query, candidates)
        finally:
            trace["verifier_ms"] = (time.perf_counter() - started) * 1000
        trace["verifier_error"] = str(error) if error else None
        for item in verifier:
            verdict = verdicts.get(item["candidate_id"])
            item["decision"] = verdict.decision if verdict else None
            item["evidence"] = verdict.visible_evidence if verdict else None
            item["accepted"] = bool(
                verdict and verdict.decision == "match" and verdict.visible_evidence.strip()
            )
        trace["verifier"] = verifier
        return verdicts, error

    class CapturingIndex(ExactVectorIndex):
        def search(self, query_vector, rows, limit=20):
            started = time.perf_counter()
            scored = super().search(query_vector, rows, limit)
            trace = traces.setdefault("current", {})
            trace["vector_search_ms"] = (time.perf_counter() - started) * 1000
            trace["indexed_segments"] = len(rows)
            trace["raw_segments"] = [
                {"asset_id": row["asset_id"], "start_frame": row["start_frame"],
                 "end_frame": row["end_frame"], "score": score}
                for score, row in scored[:20]
            ]
            return scored

    def capture_rank(scored, profiles, limit=5, refine_ranges=True):
        started = time.perf_counter()
        result = original_rank(scored, profiles, limit, refine_ranges=refine_ranges)
        trace = traces.setdefault("current", {})
        if refine_ranges:
            trace["event_rank_ms"] = (time.perf_counter() - started) * 1000
            trace["ranked_events"] = [dict(row) for row in result]
            trace["embedding_only_baseline"] = filter_visual_candidates(result)
        return result

    ai.embedding_provider = lambda: CacheGuardProvider(original_embedding_provider())
    ai.verify_visual_matches = guarded_verify_batch
    search_module.ExactVectorIndex = CapturingIndex
    search_module.rank_distinct_events = capture_rank


def main():
    args = parse_args()
    repo = Path(__file__).resolve().parents[1]
    try:
        data_dir = validate_isolated_data_dir(args.data_dir, repo)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    try:
        dataset = validate_dataset(json.loads(args.dataset.read_text()), args.profile)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        raise SystemExit(f"Invalid benchmark: {error}") from error

    os.environ["STORYROOM_DATA"] = str(data_dir)
    # This runner never enables paid-tier requests or paid fallback.
    os.environ["STORYROOM_GEMINI_TIER"] = "unpaid"
    sys.path.insert(0, str(repo))
    from fastapi.testclient import TestClient

    from server import ai, config, db
    from server import search as search_module
    from server.app import app
    if not config.UNPAID_TERMS_ACKNOWLEDGED:
        raise SystemExit("Set STORYROOM_GEMINI_UNPAID_TERMS_ACKNOWLEDGED=true to use cloud indexing/search.")
    if config.VISUAL_TIER != "unpaid":
        raise SystemExit("Refusing: visual model is not configured for the unpaid tier.")

    traces = {}
    install_instrumentation(
        ai, search_module, db, config, traces, args.allow_free_gemini
    )

    outputs = {}
    baseline_outputs = {}
    with TestClient(app, headers={"X-Storyroom": "local"}) as client:
        for row in dataset["queries"]:
            traces["current"] = {}
            started = time.perf_counter()
            response = client.post(
                f"/api/projects/{row['project_id']}/search",
                json={"query": row["query"], "mode": "visual"},
            )
            if response.status_code != 200:
                raise SystemExit(f"Query {row['id']} failed ({response.status_code}): {response.text}")
            traces["current"]["latency_ms"] = (time.perf_counter() - started) * 1000
            payload = response.json()
            returned = payload["results"]
            outputs[row["id"]] = returned
            row["trace"] = traces.get("current", {})
            row["trace"]["response_status"] = {
                key: value for key, value in payload.items() if key != "results"
            }
            baseline_outputs[row["id"]] = row["trace"].get("embedding_only_baseline", [])

    fps_by_asset = {
        video["asset_id"]: float(video.get("normalized_fps", config.FPS))
        for video in dataset["videos"]
    }
    report = evaluate_rows(dataset["queries"], outputs, fps_by_asset)
    report["embedding_only_baseline"] = evaluate_rows(
        dataset["queries"], baseline_outputs, fps_by_asset, diagnose_stages=False
    )
    report["profile"] = args.profile
    report["queries"] = [
        {"id": row["id"], "query": row["query"], "returned": outputs[row["id"]],
         "trace": row["trace"]}
        for row in dataset["queries"]
    ]
    report["request_totals"] = {
        key: sum(row["trace"].get(key, 0) for row in dataset["queries"])
        for key in (
            "query_embedding_cache_hits", "query_embedding_request_attempts",
            "verifier_cache_hits", "verifier_cache_misses", "verifier_batch_invocations",
            "verifier_request_attempts",
        )
    }
    report["model"] = config.EMBED_MODEL
    report["verifier_model"] = config.VISUAL_VERIFIER_MODEL
    report["retrieval"] = "exact cosine over locally stored visual vectors"
    report["gemini_calls_allowed"] = bool(args.allow_free_gemini)
    report["note"] = "Scores are ranking signals, not confidence probabilities."
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
