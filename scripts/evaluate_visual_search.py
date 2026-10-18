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
    return interval_iou(actual, target) >= min_iou or (
        actual[0] <= (target[0] + target[1]) / 2 <= actual[1]
    )


def evaluate_rows(rows, returned_by_id):
    """Summarize top-5 relevance, top-1 precision, negatives, and boundaries."""
    outcomes = []
    boundary_errors = []
    for row in rows:
        returned = returned_by_id[row["id"]]
        expected = row.get("relevant", [])
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
                }
            )
            continue
        matches = [
            any(candidate_matches(hit, target) for target in expected)
            for hit in returned
        ]
        top5 = any(matches)
        top1 = bool(matches and matches[0])
        matched_target = next(
            (
                target
                for hit, is_match in zip(returned, matches)
                if is_match
                for target in expected
                if candidate_matches(hit, target)
            ),
            None,
        )
        boundary_error = None
        if matched_target:
            matched_hit = next(
                hit
                for hit in returned
                if candidate_matches(hit, matched_target)
            )
            start_error = abs(
                matched_hit["start_frame"] / 30 - float(matched_target["start_sec"])
            )
            end_error = abs(
                matched_hit["end_frame"] / 30 - float(matched_target["end_sec"])
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
        "by_category": by_category,
        "by_split": by_split,
        "per_query": outcomes,
    }


def validate_dataset(dataset):
    videos = dataset.get("videos")
    queries = dataset.get("queries")
    if not isinstance(videos, list) or not isinstance(queries, list):
        raise TypeError("Dataset must contain 'videos' and 'queries' arrays.")
    if len(videos) < 50:
        raise ValueError(f"Need at least 50 videos; found {len(videos)}.")
    if len(queries) != 100:
        raise ValueError(f"Expected exactly 100 reviewed searches; found {len(queries)}.")
    categories = {video.get("category") for video in videos}
    if len(categories) < 5:
        raise ValueError("Videos must cover at least five footage categories.")
    category_counts = {
        category: sum(video.get("category") == category for video in videos)
        for category in categories
    }
    if any(count < 10 for count in category_counts.values()) or len(videos) != 50:
        raise ValueError("Use exactly 50 videos with 10 videos in each of five categories.")
    video_ids = [video.get("asset_id") for video in videos]
    if len(set(video_ids)) != len(video_ids) or None in video_ids:
        raise ValueError("Each video needs a unique indexed asset_id.")
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
    if counts != {"positive": 50, "paraphrase": 25, "negative": 25}:
        raise ValueError(f"Expected 50 positives, 25 paraphrases, 25 negatives; got {counts}.")
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


def main():
    args = parse_args()
    repo = Path(__file__).resolve().parents[1]
    try:
        data_dir = validate_isolated_data_dir(args.data_dir, repo)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    try:
        dataset = validate_dataset(json.loads(args.dataset.read_text()))
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
    from server.vector_index import ExactVectorIndex, filter_visual_candidates

    if not config.UNPAID_TERMS_ACKNOWLEDGED:
        raise SystemExit("Set STORYROOM_GEMINI_UNPAID_TERMS_ACKNOWLEDGED=true to use cloud indexing/search.")
    if config.VISUAL_TIER != "unpaid":
        raise SystemExit("Refusing: visual model is not configured for the unpaid tier.")

    traces = {}
    original_embedding_provider = ai.embedding_provider
    original_verify = ai.verify_visual_match

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
            if cached is not None:
                return cached
            if not args.allow_free_gemini:
                raise RuntimeError(f"Query vector is not cached for {query!r}; refusing a network call.")
            return self.provider.embed_text_query(query, job_id)

    ai.embedding_provider = lambda: CacheGuardProvider(original_embedding_provider())

    def guarded_verify(query, proxy, proxy_hash, start, end):
        key = ai.visual_verifier_cache_key(query, proxy_hash, start, end)
        if db.cache_get(key) is None and not args.allow_free_gemini:
            raise RuntimeError(
                f"Visual verdict is not cached for {query!r} at {start}:{end}; "
                "refusing a network call."
            )
        verdict = original_verify(query, proxy, proxy_hash, start, end)
        traces.setdefault("current", {}).setdefault("verifier", []).append({
            "asset_id": proxy.parent.name, "start_frame": start,
            "end_frame": end, "decision": verdict.decision,
            "evidence": verdict.visible_evidence,
        })
        return verdict

    ai.verify_visual_match = guarded_verify
    original_rank = search_module.rank_distinct_events

    class CapturingIndex(ExactVectorIndex):
        def search(self, query_vector, rows, limit=20):
            scored = super().search(query_vector, rows, limit)
            traces.setdefault("current", {})["raw_segments"] = [
                {"asset_id": row["asset_id"], "start_frame": row["start_frame"],
                 "end_frame": row["end_frame"], "score": score}
                for score, row in scored[:20]
            ]
            return scored

    def capture_rank(scored, profiles, limit=5, refine_ranges=True):
        result = original_rank(scored, profiles, limit, refine_ranges=refine_ranges)
        if refine_ranges:
            traces.setdefault("current", {})["ranked_events"] = [dict(row) for row in result[:20]]
            traces["current"]["embedding_only_baseline"] = filter_visual_candidates(result)
        return result

    search_module.ExactVectorIndex = CapturingIndex
    search_module.rank_distinct_events = capture_rank

    outputs = {}
    baseline_outputs = {}
    with TestClient(app, headers={"X-Storyroom": "local"}) as client:
        for row in dataset["queries"]:
            traces["current"] = {}
            response = client.post(
                f"/api/projects/{row['project_id']}/search",
                json={"query": row["query"], "mode": "visual"},
            )
            if response.status_code != 200:
                raise SystemExit(f"Query {row['id']} failed ({response.status_code}): {response.text}")
            returned = response.json()
            outputs[row["id"]] = returned
            row["trace"] = traces.get("current", {})
            baseline_outputs[row["id"]] = row["trace"].get("embedding_only_baseline", [])

    report = evaluate_rows(dataset["queries"], outputs)
    report["embedding_only_baseline"] = evaluate_rows(dataset["queries"], baseline_outputs)
    report["model"] = config.EMBED_MODEL
    report["verifier_model"] = config.VISUAL_VERIFIER_MODEL
    report["retrieval"] = "exact cosine over locally stored visual vectors"
    report["gemini_calls_allowed"] = bool(args.allow_free_gemini)
    report["note"] = "Scores are ranking signals, not confidence probabilities."
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
