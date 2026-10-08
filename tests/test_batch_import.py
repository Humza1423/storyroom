"""Per-file contracts; requests still register one asset atomically."""

from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from server import config, db, media
from server.worker import once


def project(client):
    return client.post("/api/projects", json={"name": "Batch"}).json()["id"]


def upload(client, pid, data, name="clip.mp4"):
    return client.post(
        f"/api/projects/{pid}/import", files={"file": (name, data, "video/mp4")}
    )


def test_valid_corrupt_duplicate_and_same_name_different_bytes(client, clip):
    pid = project(client)
    original = clip.read_bytes()
    first = upload(client, pid, original).json()
    rejected = upload(client, pid, b"corrupt")
    assert rejected.status_code == 400
    assert rejected.json()["code"] == "file_invalid"
    assert rejected.json()["scope"] == "file"
    # Appended bytes preserve a valid MP4 but change its content hash.
    second = upload(client, pid, original + b"different").json()
    duplicate = upload(client, pid, original, "renamed.mp4").json()
    assert duplicate == {
        "id": first["id"],
        "job_id": first["job_id"],
        "duplicate": True,
    }
    assert second["id"] != first["id"]
    assert len(db.rows("SELECT * FROM assets")) == 2
    assert len(db.rows("SELECT * FROM jobs")) == 2
    while once():
        pass
    assets = client.get(f"/api/projects/{pid}").json()["assets"]
    assert all(a["status"] == "ready" for a in assets)
    assert all(a["preparation_job"]["status"] == "done" for a in assets)
    assert all("payload" not in a["preparation_job"] for a in assets)


@pytest.mark.parametrize(
    "failure,code,scope",
    [
        ("file_bytes", "file_too_large", "file"),
        ("capacity", "project_capacity", "batch"),
        ("disk", "disk_space", "batch"),
        ("probe", "inspection_unavailable", "batch"),
    ],
)
def test_limits_are_structured_and_leave_no_registered_asset(
    client, clip, monkeypatch, failure, code, scope
):
    pid = project(client)
    if failure == "file_bytes":
        monkeypatch.setattr(config, "MAX_BYTES", 1)
    if failure == "capacity":
        monkeypatch.setattr(config, "MAX_FILES", 0)
    if failure == "disk":
        monkeypatch.setattr(
            "server.app.shutil.disk_usage", lambda _: SimpleNamespace(free=0)
        )
    if failure == "probe":

        def unavailable(_):
            raise media.InspectionUnavailable("No inspector")

        monkeypatch.setattr(media, "probe", unavailable)
    response = upload(client, pid, clip.read_bytes())
    assert response.status_code in (400, 503)
    assert response.json()["code"] == code
    assert response.json()["scope"] == scope
    assert not response.json()["uncertain"]
    assert not db.rows("SELECT * FROM assets")
    assert not db.rows("SELECT * FROM jobs")


def test_missing_project_and_unknown_storage_errors_pause(client, clip, monkeypatch):
    missing = upload(client, "missing", clip.read_bytes())
    assert missing.status_code == 404
    assert missing.json()["code"] == "project_missing"
    pid = project(client)

    def broken(_):
        raise OSError("private internal detail")

    monkeypatch.setattr("server.app.shutil.disk_usage", broken)
    response = upload(client, pid, clip.read_bytes())
    assert response.status_code == 500
    assert response.json()["scope"] == "batch"
    assert response.json()["uncertain"]
    assert "private internal" not in response.text


def test_preparation_association_survives_activity_window_and_stale_retries(
    client, clip, monkeypatch
):
    pid = project(client)
    imported = upload(client, pid, clip.read_bytes()).json()
    aid, jid = imported["id"], imported["job_id"]
    original = config.asset_dir(aid) / "original.mp4"
    source = original.read_bytes()
    with monkeypatch.context() as failure:

        def broken(*_):
            raise ValueError("Synthetic encoding failure")

        failure.setattr(media, "normalize", broken)
        assert once()
    assert db.one("SELECT status FROM assets WHERE id=?", (aid,))["status"] == "failed"
    for i in range(45):
        job = db.enqueue(pid, "export", {"fixture": i})
        db.execute("UPDATE jobs SET status='done' WHERE id=?", (job,))
    details = client.get(f"/api/projects/{pid}").json()
    assert jid not in {j["id"] for j in details["jobs"]}
    assert details["assets"][0]["preparation_job"]["id"] == jid
    duplicate = upload(client, pid, source).json()
    assert duplicate["job_id"] == jid
    retry = client.post(f"/api/jobs/{jid}/retry").json()["job_id"]
    assert client.post(f"/api/jobs/{jid}/retry").json()["job_id"] == retry
    assert once()
    # A stale button must not create another encoding after the replacement finished.
    assert client.post(f"/api/jobs/{jid}/retry").json()["job_id"] == retry
    latest = client.get(f"/api/projects/{pid}").json()["assets"][0]
    assert latest["status"] == "ready"
    assert latest["preparation_job"]["id"] == retry
    assert len(db.rows("SELECT * FROM jobs WHERE kind='normalize'")) == 2
    assert original.read_bytes() == source
    assert len(db.rows("SELECT * FROM assets")) == 1


@pytest.mark.parametrize("cancelled", [False, True])
def test_failed_preparation_and_asset_become_visible_atomically(
    client, clip, monkeypatch, cancelled
):
    pid = project(client)
    imported = upload(client, pid, clip.read_bytes()).json()
    original_connect = db.connect
    observed = []

    @contextmanager
    def observe_commits():
        with original_connect() as connection:
            yield connection
        # A second connection sees exactly what an API retry could see between
        # worker transactions. It must never see a retryable job with stale asset state.
        with original_connect() as reader:
            states = reader.execute(
                "SELECT j.status, a.status FROM jobs j JOIN assets a ON a.id=? WHERE j.id=?",
                (imported["id"], imported["job_id"]),
            ).fetchone()
            observed.append(tuple(states))

    def broken(*_):
        if cancelled:
            raise media.Cancelled()
        raise ValueError("Synthetic preparation failure")

    monkeypatch.setattr(db, "connect", observe_commits)
    monkeypatch.setattr(media, "normalize", broken)
    assert once()
    status = "cancelled" if cancelled else "failed"
    assert (status, "failed") in observed
    assert (status, "processing") not in observed
