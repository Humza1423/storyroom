"""Run frozen Gemini activity queries through the real API and worker, unpaid only."""

import argparse
import hashlib
import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace


def hit(candidate, target):
    if candidate["asset_id"] != target["asset_id"]:
        return False
    left, right = candidate["start_frame"] / 30, candidate["end_frame"] / 30
    start, end = target["start_sec"], target["end_sec"]
    overlap = max(0, min(right, end) - max(left, start))
    if target.get("label_type") == "presence":
        return overlap / max(1 / 30, right - left) >= 0.9
    return overlap / max(1 / 30, max(right, end) - min(left, start)) >= 0.5


def score(rows, key):
    expected = {row["id"]: row for row in key["queries"]}
    positive = [r for r in rows if expected[r["id"]]["kind"] != "negative"]
    negative = [r for r in rows if expected[r["id"]]["kind"] == "negative"]

    def matches(row, first=False):
        results = row.get("results", [])[: 1 if first else 5]
        return any(hit(c, t) for c in results for t in expected[row["id"]]["relevant"])

    returned = [r for r in rows if r.get("results")]
    durations = [r for r in positive if expected[r["id"]].get("requested_duration_sec")]
    boundaries = []
    for r in positive:
        for c in r.get("results", [])[:1]:
            for t in expected[r["id"]]["relevant"]:
                if t.get("activity_kind") == "discrete" and hit(c, t):
                    boundaries.append(
                        max(
                            abs(c["start_frame"] / 30 - t["start_sec"]),
                            abs(c["end_frame"] / 30 - t["end_sec"]),
                        )
                    )
                    break
    return {
        "queries_completed": len(rows),
        "positive_queries": len(positive),
        "negative_queries": len(negative),
        "top5_relevant": sum(matches(r) for r in positive),
        "top1_relevant": sum(matches(r, True) for r in positive),
        "returned_first_precision": {
            "correct": sum(matches(r, True) for r in returned),
            "returned": len(returned),
        },
        "negative_false_returns": sum(bool(r.get("results")) for r in negative),
        "provider_or_validation_errors": sum(
            bool(r.get("error"))
            or r.get("inspection_status") in ("failed", "cancelled")
            or r.get("status", {}).get("checked_candidates", 5) < 5
            for r in rows
        ),
        "duration_queries": len(durations),
        "duration_fulfilled_with_relevant_cut": sum(
            any(
                hit(c, t)
                and c["end_frame"] - c["start_frame"]
                == round(expected[r["id"]]["requested_duration_sec"] * 30)
                for c in r.get("results", [])
                for t in expected[r["id"]]["relevant"]
            )
            for r in durations
        ),
        "median_discrete_boundary_error_sec": statistics.median(boundaries)
        if boundaries
        else None,
        "boundary_labels_matched": len(boundaries),
        "p50_total_seconds": statistics.median(r["total_seconds"] for r in rows)
        if rows
        else None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path("data/evaluation/gemini-fresh")
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--ids", help="Optional development subset, comma separated")
    parser.add_argument("--allow-free-gemini", action="store_true")
    args = parser.parse_args()
    if not args.allow_free_gemini:
        parser.error("Explicit --allow-free-gemini is required")
    root = args.root.resolve()
    key_bytes = (root / "answer-key-frozen-v1.json").read_bytes()
    key = json.loads((root / "answer-key-mapped-v1.json").read_text())
    os.environ["STORYROOM_DATA"] = str(root / "session")
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from fastapi.testclient import TestClient

    from server import ai, config, db, worker
    from server.app import app

    if config.VISUAL_TIER != "unpaid" or not config.visual_ai_ready():
        parser.error(
            "Configure existing unpaid Gemini access; this runner never enables paid access"
        )
    output = args.output or root / "activity-validation.json"
    identity = {
        "code_revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
        "embedding_model": config.EMBED_MODEL,
        "verifier_model": config.VISUAL_VERIFIER_MODEL,
        "frozen_key_sha256": hashlib.sha256(key_bytes).hexdigest(),
        "data_dir": str(config.DATA),
    }
    report = {**identity, "queries": []}
    if output.exists():
        report = json.loads(output.read_text())
        if any(report.get(k) != value for k, value in identity.items()):
            parser.error("Evidence identity changed; choose a new output file")
    done = {q["id"] for q in report["queries"]}
    selected = set(args.ids.split(",")) if args.ids else None
    counts = {}
    original_client = ai.embedding_client

    def observed_client():
        client = original_client()

        def embed(**kwargs):
            counts["embedding_requests"] += 1
            return client.models.embed_content(**kwargs)

        def generate(**kwargs):
            counts["video_requests"] += 1
            return client.models.generate_content(**kwargs)

        return SimpleNamespace(
            models=SimpleNamespace(embed_content=embed, generate_content=generate),
            close=client.close,
        )

    ai.embedding_client = observed_client
    with TestClient(app, headers={"X-Storyroom": "local"}) as client:
        for row in key["queries"]:
            if row["id"] in done or selected is not None and row["id"] not in selected:
                continue
            counts.update(embedding_requests=0, video_requests=0)
            started = time.perf_counter()
            item = {"id": row["id"], "query": row["query"], "results": []}
            try:
                response = client.post(
                    f"/api/projects/{row['project_id']}/search",
                    json={"query": row["query"], "mode": "visual", "grounded": True},
                )
                response.raise_for_status()
                body = response.json()
                item.update(
                    results=body.pop("results"),
                    status=body,
                    initial_seconds=time.perf_counter() - started,
                )
                if job_id := body.get("activity_job_id"):
                    # This isolated runner owns its worker; the interactive app
                    # must not use the same evaluation data directory concurrently.
                    while (
                        db.one("SELECT status FROM jobs WHERE id=?", (job_id,))[
                            "status"
                        ]
                        == "queued"
                    ):
                        if not worker.once():
                            break
                    job = db.one("SELECT * FROM jobs WHERE id=?", (job_id,))
                    saved = json.loads(job["result"] or "{}")
                    item.update(
                        results=saved.get("visual_results", item["results"]),
                        inspection_status=job["status"],
                        inspection_message=job["message"],
                        continuation_diagnostics=saved.get(
                            "inspection_diagnostics", {}
                        ),
                    )
            except Exception as exc:  # noqa: BLE001 - retain every failed query in evaluation
                item["error"] = type(exc).__name__
            item.update(counts, total_seconds=time.perf_counter() - started)
            report["queries"].append(item)
            report["summary"] = score(report["queries"], key)
            output.write_text(json.dumps(report, indent=2) + "\n")
            print(
                json.dumps(
                    {k: v for k, v in item.items() if k not in ("results", "status")}
                ),
                flush=True,
            )
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    main()
