"""Bounded development comparison; never enables paid access or changes labels."""

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--ids", default="p01,p02,p03,p19")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--allow-free-gemini", action="store_true")
    args = parser.parse_args()
    data = args.data_dir.resolve()
    if data == ROOT / "data" or not (data / "storyroom.sqlite").is_file():
        parser.error("Choose an existing isolated evaluation database")
    if not args.allow_free_gemini:
        parser.error(
            "Explicit --allow-free-gemini is required for this live experiment"
        )
    os.environ["STORYROOM_DATA"] = str(data)
    sys.path.insert(0, str(ROOT))
    from server import config, db
    from server.search import search_visual

    if config.VISUAL_TIER != "unpaid":
        parser.error("This comparison never uses the paid tier")
    dataset = json.loads(args.dataset.read_text())
    selected = set(args.ids.split(","))
    report = {"dataset": str(args.dataset), "data_dir": str(data), "queries": []}
    for row in dataset["queries"]:
        if row["id"] not in selected:
            continue
        started = time.perf_counter()
        usage_before = db.one("SELECT count(*) AS n FROM usage")["n"]
        status = {}
        try:
            results = search_visual(
                row["project_id"], row["query"], status=status, grounded=True
            )
            initial_ms = round((time.perf_counter() - started) * 1000, 1)
            job_id = status.get("activity_job_id")
            if job_id:
                deadline = time.monotonic() + 180
                while time.monotonic() < deadline:
                    job = db.one("SELECT * FROM jobs WHERE id=?", (job_id,))
                    if job["status"] in ("done", "failed", "cancelled"):
                        saved = json.loads(job["result"] or "{}")
                        results = saved.get("visual_results", results)
                        status["inspection_status"] = job["status"]
                        status["inspection_message"] = job["message"]
                        break
                    time.sleep(0.5)
                else:
                    status["inspection_status"] = "timeout_still_running"
            item = {
                "id": row["id"],
                "query": row["query"],
                "results": results,
                "status": status,
                "initial_ms": initial_ms,
                "total_ms": round((time.perf_counter() - started) * 1000, 1),
                "usage_records_added": db.one("SELECT count(*) AS n FROM usage")["n"]
                - usage_before,
            }
        except Exception as exc:  # noqa: BLE001 - keep bounded experiment evidence on failures
            item = {"id": row["id"], "query": row["query"], "error": type(exc).__name__}
        report["queries"].append(item)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2))
        print(json.dumps({k: v for k, v in item.items() if k != "results"}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
