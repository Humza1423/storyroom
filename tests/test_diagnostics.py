import json

import pytest
from conftest import create_ready

from server import config, db, media
from server.diagnostics import MediaDiagnostics
from server.worker import once


def test_stage_timing_uses_injected_monotonic_clock_and_keeps_output_size(tmp_path):
    now = [4.0]
    snapshots = []
    recorder = MediaDiagnostics(
        on_change=snapshots.append,
        clock=lambda: now[0],
    )
    output = tmp_path / "edit.mp4"

    def create_output():
        now[0] += 0.125678
        output.write_bytes(b"frames")

    recorder.measure("editing_copy", create_output, output)
    assert recorder.snapshot()["stages"]["editing_copy"] == {
        "status": "complete",
        "elapsed_seconds": 0.1257,
        "output_bytes": 6,
    }
    assert snapshots[0]["stages"]["editing_copy"]["status"] == "running"


def test_stage_failure_and_cancellation_preserve_earlier_measurements(tmp_path):
    recorder = MediaDiagnostics(
        clock=lambda: 1.0,
        is_cancelled=lambda exc: isinstance(exc, media.Cancelled),
    )
    output = tmp_path / "edit.mp4"
    output.write_bytes(b"source")
    recorder.measure("editing_copy", lambda: None, output)

    with pytest.raises(media.Cancelled):
        recorder.measure(
            "proxy",
            lambda: (_ for _ in ()).throw(media.Cancelled("Cancelled")),
            tmp_path / "proxy.mp4",
        )

    snapshot = recorder.snapshot()
    assert snapshot["stages"]["editing_copy"]["status"] == "complete"
    assert snapshot["stages"]["proxy"]["status"] == "cancelled"
    assert snapshot["stages"]["proxy"]["error_type"] == "Cancelled"


def test_render_part_rollup_stays_bounded_for_three_thousand_placements(tmp_path):
    now = [0.0]
    snapshots = []
    recorder = MediaDiagnostics(on_change=snapshots.append, clock=lambda: now[0])
    part = tmp_path / "part.mov"

    for index in range(3000):
        now[0] += (index % 7) / 1000
        part.write_bytes(b"part")
        recorder.render_part(index, lambda: None, part)
    recorder.finish_parts()

    result = recorder.snapshot()["render_parts"]
    assert result["status"] == "complete"
    assert result["attempted_parts"] == result["completed_parts"] == 3000
    assert result["output_bytes"] == 3000 * 4
    assert len(result["slowest_parts"]) == recorder.MAX_SLOW_PARTS
    assert len(json.dumps(recorder.snapshot())) < 8192
    # Persistence is batched. It does not write once for every storyboard cut.
    assert len(snapshots) < 100


def test_worker_persists_completed_stages_on_normalization_cancellation(
    client, clip, monkeypatch
):
    pid = client.post("/api/projects", json={"name": "Cancellation"}).json()["id"]
    with clip.open("rb") as source:
        response = client.post(
            f"/api/projects/{pid}/import",
            files={"file": ("sample.mp4", source, "video/mp4")},
        )
    assert response.status_code == 200
    asset_id = response.json()["id"]
    job = db.one("SELECT id FROM jobs WHERE project_id=?", (pid,))
    original_encode = media.encode
    count = 0

    def cancel_between_media_stages(*args, **kwargs):
        nonlocal count
        count += 1
        if count == 2:
            db.execute("UPDATE jobs SET cancel=1 WHERE id=?", (job["id"],))
        return original_encode(*args, **kwargs)

    monkeypatch.setattr(media, "encode", cancel_between_media_stages)
    assert once()
    saved = db.one("SELECT status,result FROM jobs WHERE id=?", (job["id"],))
    result = json.loads(saved["result"])
    stages = result["diagnostics"]["stages"]
    assert saved["status"] == "cancelled"
    assert stages["editing_copy"]["status"] == "complete"
    assert stages["editing_copy"]["output_bytes"] > 0
    assert stages["proxy"]["status"] == "cancelled"
    assert "thumbnail" not in stages
    assert (
        db.one("SELECT status FROM assets WHERE id=?", (asset_id,))["status"]
        == "failed"
    )


def test_worker_render_failure_keeps_completed_part_measurements(
    client, clip, monkeypatch
):
    pid, asset_id = create_ready(client, clip)
    board = [
        {
            "id": "section",
            "title": "Practice",
            "purpose": "",
            "selections": [
                {
                    "id": f"cut-{index}",
                    "asset_id": asset_id,
                    "moment_id": asset_id,
                    "start_frame": index,
                    "end_frame": index + 8,
                    "note": "",
                }
                for index in range(3)
            ],
        }
    ]
    assert (
        client.put(
            f"/api/projects/{pid}/board", json={"revision": 0, "sections": board}
        ).status_code
        == 200
    )
    job_id = client.post(f"/api/projects/{pid}/jobs/render", json={"query": ""}).json()[
        "job_id"
    ]
    original_run = media.run
    part_count = 0

    def fail_second_part(args, cancelled=lambda: False):
        nonlocal part_count
        if str(args[-1]).endswith(".mov"):
            part_count += 1
            if part_count == 2:
                raise ValueError("controlled media failure")
        return original_run(args, cancelled)

    monkeypatch.setattr(media, "run", fail_second_part)
    assert once()
    job = db.one("SELECT status,result FROM jobs WHERE id=?", (job_id,))
    diagnostics = json.loads(job["result"])["diagnostics"]["render_parts"]
    assert job["status"] == "failed"
    assert diagnostics["status"] == "failed"
    assert diagnostics["completed_parts"] == 1
    assert diagnostics["attempted_parts"] == 2
    assert diagnostics["output_bytes"] > 0
    assert diagnostics["failed_part"] == 1


def test_legacy_job_result_without_diagnostics_still_loads(client):
    pid = client.post("/api/projects", json={"name": "Old result"}).json()["id"]
    job_id = db.enqueue(pid, "render", {})
    legacy_result = {"url": f"/api/jobs/{job_id}/download"}
    db.execute(
        "UPDATE jobs SET status='done',result=? WHERE id=?",
        (json.dumps(legacy_result), job_id),
    )
    response = client.get(f"/api/projects/{pid}")
    assert response.status_code == 200
    job = next(job for job in response.json()["jobs"] if job["id"] == job_id)
    assert job["result"] == legacy_result


def test_successful_worker_results_keep_download_url_and_stage_sizes(client, clip):
    pid, asset_id = create_ready(client, clip)
    normalize_job = db.one(
        "SELECT result FROM jobs WHERE project_id=? AND kind='normalize'", (pid,)
    )
    normalization = json.loads(normalize_job["result"])["diagnostics"]["stages"]
    folder = config.asset_dir(asset_id)
    for stage, filename in (
        ("editing_copy", "edit.mp4"),
        ("proxy", "proxy.mp4"),
        ("thumbnail", "thumb.jpg"),
    ):
        assert normalization[stage]["status"] == "complete"
        assert (
            normalization[stage]["output_bytes"] == (folder / filename).stat().st_size
        )

    board = [
        {
            "id": "section",
            "title": "Practice",
            "purpose": "",
            "selections": [
                {
                    "id": "cut",
                    "asset_id": asset_id,
                    "moment_id": asset_id,
                    "start_frame": 0,
                    "end_frame": 12,
                    "note": "",
                }
            ],
        }
    ]
    client.put(f"/api/projects/{pid}/board", json={"revision": 0, "sections": board})
    job_id = client.post(f"/api/projects/{pid}/jobs/render", json={"query": ""}).json()[
        "job_id"
    ]
    assert once()
    job = db.one("SELECT status,message,result FROM jobs WHERE id=?", (job_id,))
    assert job["status"] == "done", job["message"]
    result = json.loads(job["result"])
    assert result["url"] == f"/api/jobs/{job_id}/download"
    assert result["diagnostics"]["render_parts"]["completed_parts"] == 1
    assert result["diagnostics"]["stages"]["render_join"]["status"] == "complete"
    assert (
        result["diagnostics"]["stages"]["render_join"]["output_bytes"]
        == (config.DATA / "exports" / f"{job_id}.mp4").stat().st_size
    )
    assert client.get(f"/api/jobs/{job_id}/download").status_code == 200


def test_export_job_result_does_not_receive_empty_media_diagnostics(client, clip):
    pid, asset_id = create_ready(client, clip)
    sections = [
        {
            "id": "section",
            "title": "Practice",
            "purpose": "",
            "selections": [
                {
                    "id": "cut",
                    "asset_id": asset_id,
                    "moment_id": asset_id,
                    "start_frame": 0,
                    "end_frame": 12,
                    "note": "",
                }
            ],
        }
    ]
    client.put(f"/api/projects/{pid}/board", json={"revision": 0, "sections": sections})
    job_id = client.post(
        f"/api/projects/{pid}/jobs/export", json={"query": ""}
    ).json()["job_id"]
    assert once()
    result = json.loads(db.one("SELECT result FROM jobs WHERE id=?", (job_id,))["result"])
    assert result["url"] == f"/api/jobs/{job_id}/download"
    assert "diagnostics" not in result
