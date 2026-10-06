"""Evaluate human-authored relevance judgments; never invent a benchmark score."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import db
from server.search import search


def main():
    p = argparse.ArgumentParser()
    p.add_argument("dataset")
    p.add_argument("--semantic", action="store_true")
    args = p.parse_args()
    rows = json.loads(Path(args.dataset).read_text())
    if len(rows) < 20 or len({r["footage_group"] for r in rows}) < 3:
        raise SystemExit(
            "Provide at least 20 human-reviewed queries from at least 3 footage groups."
        )
    db.init()
    results = []
    for r in rows:
        hits = search(r["project_id"], r["query"], semantic=args.semantic, limit=5)
        success = bool({m["id"] for m in hits} & set(r["relevant_moment_ids"]))
        results.append(
            {
                "query": r["query"],
                "hit_at_5": success,
                "returned": [m["id"] for m in hits],
            }
        )
    print(
        json.dumps(
            {
                "hit_at_5": sum(r["hit_at_5"] for r in results) / len(results),
                "queries": results,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
