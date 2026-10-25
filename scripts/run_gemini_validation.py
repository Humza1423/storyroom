"""Prepare isolated real-API validation project and index reviewed video inputs.

Search evaluation is deliberately a separate step after the code is frozen.
Uses the real import API and persistent worker, one job at a time.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path("data/evaluation/gemini-fresh")
    )
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    root = args.root.resolve()
    session = root / "session"
    if (
        session == repo / "data"
        or repo / "data" in session.parents
        and root == repo / "data"
    ):
        raise SystemExit("Use an isolated evaluation directory.")
    frozen_path = root / "answer-key-frozen-v1.json"
    frozen = json.loads(frozen_path.read_text())
    sources = json.loads((root / "provenance.json").read_text())
    os.environ["STORYROOM_DATA"] = str(session)
    os.environ["STORYROOM_GEMINI_TIER"] = "unpaid"
    os.environ["STORYROOM_GEMINI_UNPAID_TERMS_ACKNOWLEDGED"] = "true"
    sys.path.insert(0, str(repo))
    from fastapi.testclient import TestClient

    from server import ai, config, db, worker
    from server.app import app

    assert config.VISUAL_TIER == "unpaid"
    if not config.visual_ai_ready():
        raise SystemExit("Gemini key is not configured; no calls made.")

    evidence_path = root / "indexing-evidence.json"
    evidence = {
        "code_revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo, text=True
        ).strip(),
        "data_dir": str(session),
        "tier": config.VISUAL_TIER,
        "model": config.EMBED_MODEL,
        "frozen_key_sha256": hashlib.sha256(frozen_path.read_bytes()).hexdigest(),
        "sdk_embedding_calls": 0,
        "sdk_internal_retries": "not exposed by SDK",
        "jobs": [],
        "errors": [],
    }

    def save():
        evidence_path.write_text(json.dumps(evidence, indent=2) + "\n")

    original_client = ai.embedding_client

    def instrumented_client():
        client = original_client()
        original_embed = client.models.embed_content

        def embed_content(**kwargs):
            evidence["sdk_embedding_calls"] += 1
            save()
            try:
                return original_embed(**kwargs)
            except Exception as exc:
                evidence["errors"].append(
                    {
                        "type": type(exc).__name__,
                        "code": getattr(exc, "code", None),
                        "status": getattr(exc, "status", None),
                    }
                )
                save()
                raise

        return SimpleNamespace(
            models=SimpleNamespace(embed_content=embed_content), close=client.close
        )

    ai.embedding_client = instrumented_client

    def request(client, method, url, **kwargs):
        response = getattr(client, method)(url, **kwargs)
        if response.status_code != 200:
            raise RuntimeError(
                f"Local API returned {response.status_code} for {url}: {response.text}"
            )
        return response.json()

    def drain():
        while worker.once():
            last = db.one(
                "SELECT id,kind,status,message,result FROM jobs ORDER BY finished DESC LIMIT 1"
            )
            evidence["jobs"].append(last)
            save()
            if last["status"] != "done":
                raise RuntimeError(
                    f"Job {last['id']} {last['status']}: {last['message']}"
                )

    mapping_path = root / "import-mapping.json"
    mapping = json.loads(mapping_path.read_text()) if mapping_path.exists() else {}
    with TestClient(app, headers={"X-Storyroom": "local"}) as client:
        if not mapping:
            mapping["project_id"] = request(
                client,
                "post",
                "/api/projects",
                json={
                    "name": "Gemini fresh validation v1",
                    "brief": "Frozen evaluation: broad activities, complete moves and durations.",
                },
            )["id"]
            mapping["assets"] = {}
            mapping_path.write_text(json.dumps(mapping, indent=2) + "\n")
        pid = mapping["project_id"]
        for source in sources:
            with (root / source["input_file"]).open("rb") as stream:
                imported = request(
                    client,
                    "post",
                    f"/api/projects/{pid}/import",
                    files={"file": (source["id"] + ".mp4", stream, "video/mp4")},
                )
            aid = imported["id"]
            mapping["assets"][source["id"]] = aid
            mapping_path.write_text(json.dumps(mapping, indent=2) + "\n")
            drain()
            request(
                client,
                "put",
                f"/api/assets/{aid}/provenance",
                json={
                    "source": source["page"],
                    "author": source["author"],
                    "license": source["license"] + " " + source["license_url"],
                    "cloud_analysis": True,
                },
            )
            print(f"Imported {source['id']}", flush=True)
        mapped = json.loads(json.dumps(frozen))
        for video in mapped["videos"]:
            video["asset_id"] = mapping["assets"][video["source_id"]]
        for query in mapped["queries"]:
            query["project_id"] = pid
            for target in query["relevant"]:
                target["asset_id"] = mapping["assets"][target["source_id"]]
        (root / "answer-key-mapped-v1.json").write_text(
            json.dumps(mapped, indent=2) + "\n"
        )
        assets = list(mapping["assets"].values())
        evidence["estimate"] = request(
            client,
            "post",
            f"/api/projects/{pid}/visual-index-estimate",
            json={"asset_ids": assets},
        )
        save()
        for source in sources:
            aid = mapping["assets"][source["id"]]
            started = time.perf_counter()
            request(
                client,
                "post",
                f"/api/projects/{pid}/visual-index",
                json={"asset_ids": [aid]},
            )
            drain()
            segments = db.one(
                "SELECT COUNT(*) AS count FROM visual_segments WHERE asset_id=?", (aid,)
            )["count"]
            evidence.setdefault("assets", []).append(
                {
                    "source_id": source["id"],
                    "asset_id": aid,
                    "segments": segments,
                    "elapsed_sec": time.perf_counter() - started,
                }
            )
            save()
            print(f"Indexed {source['id']}: {segments} segments", flush=True)
        evidence["usage"] = db.rows("SELECT model,reserved,actual,status FROM usage")
        evidence["segments"] = db.one("SELECT COUNT(*) AS count FROM visual_segments")[
            "count"
        ]
        save()
        print(
            f"Done: {evidence['segments']} segments, {evidence['sdk_embedding_calls']} SDK embedding calls. No searches executed."
        )


if __name__ == "__main__":
    main()
