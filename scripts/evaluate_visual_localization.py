"""Compare opt-in query-aware cuts with existing cuts on local sports labels.

Only the localization call may use the provider. Existing query vectors and
yes/no verifier verdicts must already be cached in an isolated evaluation DB.
The caller must explicitly allow unpaid Gemini requests; paid calls are refused.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

from evaluate_visual_search import (
    evaluate_rows,
    install_instrumentation,
    validate_dataset,
    validate_isolated_data_dir,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--allow-free-gemini", action="store_true")
    parser.add_argument("--query-id", action="append", help="Limit to a reviewed sports query ID")
    args = parser.parse_args()
    if not args.allow_free_gemini:
        raise SystemExit("Add --allow-free-gemini to authorize bounded unpaid localization calls.")

    repo = Path(__file__).resolve().parents[1]
    data_dir = validate_isolated_data_dir(args.data_dir, repo)
    dataset = validate_dataset(json.loads(args.dataset.read_text()), "smoke")
    rows = [row for row in dataset["queries"]
            if row["category"] == "sports" and row["kind"] == "positive"]
    if len(rows) != 4:
        raise SystemExit("Expected exactly four reviewed sports-positive queries.")
    if args.query_id:
        requested = set(args.query_id)
        rows = [row for row in rows if row["id"] in requested]
        if len(rows) != len(requested):
            raise SystemExit("--query-id must name a reviewed sports-positive query.")
    os.environ["STORYROOM_DATA"] = str(data_dir)
    sys.path.insert(0, str(repo))

    from fastapi.testclient import TestClient

    from server import ai, config, db
    from server import search as search_module
    from server.app import app

    if config.VISUAL_TIER != "unpaid" or not config.UNPAID_TERMS_ACKNOWLEDGED:
        raise SystemExit("This comparison requires acknowledged unpaid Gemini access.")
    if not config.visual_ai_ready():
        raise SystemExit("Visual AI is not configured; no cloud request was made.")

    traces = {}
    # Prevent accidental fresh embedding or yes/no verification requests. Only
    # the new opt-in localization method is allowed to contact Gemini.
    install_instrumentation(ai, search_module, db, config, traces, False)
    baseline = {}
    experiment = {}
    details = []
    with TestClient(app, headers={"X-Storyroom": "local"}) as client:
        for row in rows:
            route = f"/api/projects/{row['project_id']}/search"
            request = {"query": row["query"], "mode": "visual"}
            old = client.post(route, json=request)
            if old.status_code != 200:
                raise SystemExit(
                    f"Cached baseline unavailable for {row['id']} "
                    f"(HTTP {old.status_code}); no localization requested."
                )
            before = len(db.rows("SELECT id FROM usage"))
            started = time.perf_counter()
            new = client.post(
                route, json={**request, "experimental_localization": True}
            )
            elapsed = time.perf_counter() - started
            if new.status_code != 200:
                raise SystemExit(f"Experimental search failed for {row['id']} (HTTP {new.status_code}).")
            old_result = old.json()
            new_result = new.json()
            baseline[row["id"]] = old_result["results"]
            experiment[row["id"]] = new_result["results"]
            details.append({
                "id": row["id"], "query": row["query"],
                "baseline": [{"asset_id": hit["asset_id"],
                              "start_frame": hit["start_frame"],
                              "end_frame": hit["end_frame"]}
                             for hit in old_result["results"]],
                "experimental": [{"asset_id": hit["asset_id"],
                                  "start_frame": hit["start_frame"],
                                  "end_frame": hit["end_frame"]}
                                 for hit in new_result["results"]],
                "warning": new_result.get("warning"),
                "elapsed_seconds": round(elapsed, 2),
                "additional_api_reservations": len(db.rows("SELECT id FROM usage")) - before,
            })

    fps = {video["asset_id"]: video.get("normalized_fps", 30)
           for video in dataset["videos"]}
    old_score = evaluate_rows(rows, baseline, fps, diagnose_stages=False)
    new_score = evaluate_rows(rows, experiment, fps, diagnose_stages=False)
    print(json.dumps({
        "profile": "sports-positive-development-only",
        "baseline": {key: old_score[key] for key in (
            "positive_asset_top5_recall", "positive_top5_recall",
            "positive_top1_accuracy", "median_boundary_error_sec",
        )},
        "experimental": {key: new_score[key] for key in (
            "positive_asset_top5_recall", "positive_top5_recall",
            "positive_top1_accuracy", "median_boundary_error_sec",
        )},
        "queries": details,
        "additional_api_reservations": sum(
            item["additional_api_reservations"] for item in details
        ),
    }, indent=2))


if __name__ == "__main__":
    main()
