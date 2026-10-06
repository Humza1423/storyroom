import pytest
import opentimelineio as otio
from server import db, config, media
from server.worker import once
from conftest import create_ready


def board(aid):
    return [
        {
            "id": "section1",
            "title": "Show the work",
            "purpose": "Practice",
            "selections": [
                {
                    "id": "clip1",
                    "asset_id": aid,
                    "moment_id": aid,
                    "start_frame": 3,
                    "end_frame": 24,
                    "note": "Keep the action",
                }
            ],
        }
    ]


def test_import_normalize_duplicate_and_original_unchanged(client, clip):
    source = clip.read_bytes()
    pid, aid = create_ready(client, clip)
    assert (config.asset_dir(aid) / "original.mp4").read_bytes() == source
    assert db.one("SELECT frames FROM assets WHERE id=?", (aid,))["frames"] == 30
    with clip.open("rb") as f:
        r = client.post(f"/api/projects/{pid}/import", files={"file": ("same.mp4", f)})
    assert r.json()["duplicate"]
    assert len(client.get(f"/api/projects/{pid}").json()["assets"]) == 1
    response = client.get(f"/api/assets/{aid}/proxy", headers={"Range": "bytes=0-99"})
    assert response.status_code == 206 and len(response.content) == 100


def test_board_save_reopen_conflict_undo(client, clip):
    pid, aid = create_ready(client, clip)
    first = board(aid)
    assert (
        client.put(
            f"/api/projects/{pid}/board", json={"revision": 0, "sections": first}
        ).status_code
        == 200
    )
    assert client.get(f"/api/projects/{pid}").json()["board"] == first
    assert (
        client.put(
            f"/api/projects/{pid}/board", json={"revision": 0, "sections": []}
        ).status_code
        == 409
    )
    assert (
        client.post(f"/api/projects/{pid}/undo", json={"revision": 0}).status_code
        == 409
    )
    assert (
        client.post(f"/api/projects/{pid}/undo", json={"revision": 1}).status_code
        == 200
    )
    assert client.get(f"/api/projects/{pid}").json()["board"] == []


@pytest.mark.parametrize("start,end", [(-1, 10), (10, 10), (20, 10), (0, 31)])
def test_invalid_boundaries_rejected(client, clip, start, end):
    pid, aid = create_ready(client, clip)
    b = board(aid)
    b[0]["selections"][0].update(start_frame=start, end_frame=end)
    assert client.put(
        f"/api/projects/{pid}/board", json={"revision": 0, "sections": b}
    ).status_code in (400, 422)


def test_foreign_assets_rejected(client, clip):
    pid, aid = create_ready(client, clip)
    other = client.post("/api/projects", json={"name": "Other"}).json()["id"]
    assert (
        client.put(
            f"/api/projects/{other}/board", json={"revision": 0, "sections": board(aid)}
        ).status_code
        == 400
    )


def test_export_reimport_and_render_exact_ranges(client, clip):
    pid, aid = create_ready(client, clip)
    b = board(aid)
    b[0]["selections"].append(
        {**b[0]["selections"][0], "id": "clip2", "start_frame": 0, "end_frame": 15}
    )
    client.put(
        f"/api/projects/{pid}/board", json={"revision": 0, "sections": b}
    ).raise_for_status()
    jid = client.post(f"/api/projects/{pid}/jobs/export", json={"query": ""}).json()[
        "job_id"
    ]
    once()
    job = db.one("SELECT * FROM jobs WHERE id=?", (jid,))
    assert job["status"] == "done", job["message"]
    timeline = otio.adapters.read_from_file(
        str(config.DATA / "exports" / f"{jid}.xml"), adapter_name="fcp_xml"
    )
    clips = list(timeline.video_tracks()[0])
    assert len(clips) == 2
    assert clips[0].source_range.start_time.value == 3
    assert clips[0].source_range.duration.value == 21
    assert clips[1].source_range.duration.value == 15
    assert client.get(f"/api/jobs/{jid}/download").status_code == 200
    render_id = client.post(
        f"/api/projects/{pid}/jobs/render", json={"query": ""}
    ).json()["job_id"]
    once()
    job = db.one("SELECT * FROM jobs WHERE id=?", (render_id,))
    assert job["status"] == "done", job["message"]
    info = media.probe(config.DATA / "exports" / f"{render_id}.mp4")
    assert abs(info["frames"] - 36) <= 1
    assert info["has_audio"]  # synthesized silence for silent input


def test_missing_media_fails_export_helpfully(client, clip):
    pid, aid = create_ready(client, clip)
    client.put(
        f"/api/projects/{pid}/board", json={"revision": 0, "sections": board(aid)}
    ).raise_for_status()
    (config.asset_dir(aid) / "edit.mp4").unlink()
    jid = client.post(f"/api/projects/{pid}/jobs/export", json={"query": ""}).json()[
        "job_id"
    ]
    once()
    job = db.one("SELECT * FROM jobs WHERE id=?", (jid,))
    assert job["status"] == "failed" and "Missing editing copy" in job["message"]


def test_manual_search_and_empty_results(client, clip):
    pid, aid = create_ready(client, clip)
    client.post(
        f"/api/assets/{aid}/moments",
        json={
            "start_frame": 0,
            "end_frame": 20,
            "description": "Basketball close-up warmup",
        },
    ).raise_for_status()
    results = client.post(
        f"/api/projects/{pid}/search", json={"query": "basketball"}
    ).json()
    assert len(results) == 1 and results[0]["start_frame"] == 0
    assert (
        client.post(f"/api/projects/{pid}/search", json={"query": "elephant"}).json()
        == []
    )


def test_bad_media_and_origin_rejected(client):
    pid = client.post("/api/projects", json={"name": "Test"}).json()["id"]
    assert (
        client.post(
            f"/api/projects/{pid}/import", files={"file": ("corrupt.mp4", b"garbage")}
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/projects",
            json={"name": "bad"},
            headers={"Origin": "https://evil.example"},
        ).status_code
        == 403
    )
    assert (
        client.get("/api/status", headers={"Host": "evil.example"}).status_code == 403
    )


def test_job_cancel_retry_deduplicates(client):
    pid = client.post("/api/projects", json={"name": "Test"}).json()["id"]
    jid = db.enqueue(pid, "render", {"board": []})
    assert jid == db.enqueue(pid, "render", {"board": []})
    assert client.post(f"/api/jobs/{jid}/cancel").status_code == 200
    assert not once()
    new = client.post(f"/api/jobs/{jid}/retry").json()["job_id"]
    assert new != jid


def test_budget_atomic_reservation_and_settlement(client, monkeypatch):
    monkeypatch.setattr(config, "SPEND_LIMIT", 1)
    uid = db.reserve(None, "test", 0.7)
    with pytest.raises(ValueError):
        db.reserve(None, "test", 0.4)
    db.execute("UPDATE usage SET actual=.1,status='settled' WHERE id=?", (uid,))
    db.reserve(None, "test", 0.4)
    assert db.spend() == pytest.approx(0.5)


def test_ai_disabled_no_money_spent(client, clip):
    pid, aid = create_ready(client, clip)
    assert (
        client.post(
            f"/api/projects/{pid}/analyze", json={"asset_ids": [aid]}
        ).status_code
        == 400
    )
    assert db.spend() == 0


def test_feedback_requires_explicit_training_permission(client, clip):
    pid, aid = create_ready(client, clip)
    payload = {
        "moment_id": aid,
        "section": "Practice",
        "rating": 2,
        "reason": "Clear movement",
        "footage_group": "shoot-a",
    }
    assert client.post(f"/api/projects/{pid}/feedback", json=payload).status_code == 400
    client.put(
        f"/api/assets/{aid}/provenance",
        json={"license": "Owned fixture", "training": True},
    ).raise_for_status()
    client.post(f"/api/projects/{pid}/feedback", json=payload).raise_for_status()
    assert len(client.get("/api/feedback").json()) == 1


@pytest.mark.parametrize(
    "patch",
    [
        {"codec": "hevc"},
        {"transfer": "smpte2084"},
        {"width": 3840},
        {"pix_fmt": "yuv420p10le"},
    ],
)
def test_input_profiles(patch):
    info = {
        "codec": "h264",
        "format": "mov,mp4",
        "width": 1920,
        "height": 1080,
        "transfer": "bt709",
        "pix_fmt": "yuv420p",
    }
    info.update(patch)
    with pytest.raises(ValueError):
        media.validate(info)


def test_portrait_supported():
    media.validate(
        {
            "codec": "h264",
            "format": "mov,mp4",
            "width": 1080,
            "height": 1920,
            "transfer": "bt709",
            "pix_fmt": "yuv420p",
        }
    )
