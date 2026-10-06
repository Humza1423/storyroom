"""Import failure tests use real SQLite and isolated generated footage."""

import json
import sqlite3

import pytest

from server import config, db
from server.worker import once


def test_failed_queue_insert_rolls_back_import_and_allows_retry(client, clip):
    pid = client.post("/api/projects", json={"name": "Import recovery"}).json()["id"]
    source = clip.read_bytes()
    # Simulate a database failure at the exact point where the job is recorded.
    db.execute("""
        CREATE TRIGGER fail_job_insert BEFORE INSERT ON jobs BEGIN
            SELECT RAISE(ABORT, 'simulated queue failure');
        END
    """)
    with clip.open("rb") as f:
        with pytest.raises(sqlite3.IntegrityError, match="simulated queue failure"):
            client.post(f"/api/projects/{pid}/import", files={"file": ("clip.mp4", f)})

    assert db.rows("SELECT * FROM assets WHERE project_id=?", (pid,)) == []
    assert db.rows("SELECT * FROM jobs WHERE project_id=?", (pid,)) == []
    assert list((config.DATA / "incoming").iterdir()) == []
    assert list((config.DATA / "media").iterdir()) == []
    assert clip.read_bytes() == source

    db.execute("DROP TRIGGER fail_job_insert")
    with clip.open("rb") as f:
        response = client.post(
            f"/api/projects/{pid}/import", files={"file": ("clip.mp4", f)}
        )
    response.raise_for_status()
    imported = response.json()
    assert imported["duplicate"] is False
    job = db.one("SELECT * FROM jobs WHERE id=?", (imported["job_id"],))
    assert job["status"] == "queued"
    assert json.loads(job["payload"]) == {"asset_id": imported["id"]}
    assert once()
    assert (
        db.one("SELECT status FROM assets WHERE id=?", (imported["id"],))["status"]
        == "ready"
    )


def test_duplicate_upload_before_processing_keeps_one_job_and_source(client, clip):
    pid = client.post("/api/projects", json={"name": "Duplicate import"}).json()["id"]
    results = []
    for name in ("clip.mp4", "renamed.mp4"):
        with clip.open("rb") as f:
            response = client.post(
                f"/api/projects/{pid}/import", files={"file": (name, f)}
            )
        response.raise_for_status()
        results.append(response.json())
    assert results[0]["id"] == results[1]["id"]
    assert results[1]["duplicate"] is True
    assert len(db.rows("SELECT * FROM assets WHERE project_id=?", (pid,))) == 1
    assert len(db.rows("SELECT * FROM jobs WHERE project_id=?", (pid,))) == 1
    assert (
        config.asset_dir(results[0]["id"]) / "original.mp4"
    ).read_bytes() == clip.read_bytes()
    assert list((config.DATA / "incoming").iterdir()) == []
