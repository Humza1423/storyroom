"""Train a small ranking experiment from explicitly permitted human judgments."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import ndcg_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from server import db, config


def evaluate(rows, scores):
    groups = {}
    for row, score in zip(rows, scores):
        key = (row["footage_group"], row["brief"], row["section"])
        groups.setdefault(key, []).append((row["rating"], float(score)))
    values = []
    hits = []
    for entries in groups.values():
        if len(entries) < 2 or not any(r > 0 for r, _ in entries):
            continue
        labels, rank = zip(*entries)
        values.append(float(ndcg_score([labels], [rank], k=5)))
        hits.append(any(r == 2 for r, _ in sorted(entries, key=lambda e: -e[1])[:5]))
    return {
        "ndcg_at_5": float(np.mean(values)) if values else None,
        "strong_fit_hit_at_5": float(np.mean(hits)) if hits else None,
        "query_groups": len(values),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(config.DATA / "training"))
    args = parser.parse_args()
    db.init()
    rows = db.rows(
        "SELECT f.*,a.provenance,a.hash FROM feedback f JOIN moments m ON m.id=f.moment_id JOIN assets a ON a.id=m.asset_id ORDER BY f.created"
    )
    rows = [r for r in rows if json.loads(r["provenance"]).get("training")]
    # Keep last judgment per moment/brief/section. Repeat clicks are not extra evidence.
    rows = list({(r["moment_id"], r["brief"], r["section"]): r for r in rows}.values())
    groups = {r["footage_group"] for r in rows}
    if len(rows) < 30 or len(groups) < 3:
        raise SystemExit(
            "Need at least 30 permitted human judgments across 3 footage groups for an exploratory run; aim for 300–500. No model trained."
        )
    hashes = {}
    for r in rows:
        hashes.setdefault(r["hash"], set()).add(r["footage_group"])
    if any(len(g) > 1 for g in hashes.values()):
        raise SystemExit(
            "The same source appears in multiple footage groups. Correct the groups before splitting."
        )
    x = np.array([json.loads(r["features"]) for r in rows])
    y = np.array([int(r["rating"] == 2) for r in rows])
    train, test = next(
        GroupShuffleSplit(n_splits=1, test_size=0.3, random_state=42).split(
            x, y, [r["footage_group"] for r in rows]
        )
    )
    if len(set(y[train])) < 2 or len(set(y[test])) < 2:
        raise SystemExit(
            "Both train and held-out footage need positive and negative judgments. Add labels; do not tune the split to improve results."
        )
    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(
            C=1, class_weight="balanced", random_state=42, max_iter=1000
        ),
    )
    model.fit(x[train], y[train])
    scores = model.predict_proba(x[test])[:, 1]
    baseline = np.where(
        x[test, 1] != 0,
        0.35 * x[test, 0] + 0.65 * np.maximum(x[test, 1], 0),
        x[test, 0],
    )
    held = [rows[i] for i in test]
    learned = evaluate(held, scores)
    base = evaluate(held, baseline)
    improved = (
        learned["ndcg_at_5"] is not None
        and base["ndcg_at_5"] is not None
        and learned["ndcg_at_5"] > base["ndcg_at_5"]
    )
    report = {
        "training_rows": len(train),
        "held_out_rows": len(test),
        "held_out_groups": sorted({r["footage_group"] for r in held}),
        "baseline": base,
        "trained": learned,
        "improved_on_this_split": improved,
        "production_enabled": False,
        "limitations": "Small exploratory test. Not proof of generalization; no automatic promotion.",
    }
    folder = Path(args.output)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "report.json").write_text(json.dumps(report, indent=2))
    # Portable coefficients instead of unsafe pickle artifacts.
    scaler = model.named_steps["standardscaler"]
    reg = model.named_steps["logisticregression"]
    artifact = {
        "features": [
            "lexical_overlap",
            "embedding_similarity",
            "duration_capped_30s",
            "no_uncertainty",
        ],
        "mean": scaler.mean_.tolist(),
        "scale": scaler.scale_.tolist(),
        "coef": reg.coef_[0].tolist(),
        "intercept": reg.intercept_[0],
        "schema_version": 1,
        "production_enabled": False,
    }
    (folder / "ranker.json").write_text(json.dumps(artifact, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
