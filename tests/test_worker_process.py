"""Real worker subprocess recovery, using only generated media and temporary data."""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

import pytest

from server import config, db
from conftest import create_ready

ROOT = Path(__file__).parents[1]


def wait_for(predicate, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(.025)
    raise AssertionError("Timed out waiting for worker state")


def stop(process):
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait(timeout=5)


@pytest.mark.parametrize("kind", ["normalize", "render"])
def test_pending_interrupted_and_retry_preserve_choices(client, clip, tmp_path, kind):
    pid, aid = create_ready(client, clip)
    board = [{"id": "s", "title": "Practice", "purpose": "", "selections": [
        {"id": "one", "asset_id": aid, "moment_id": aid, "start_frame": 2, "end_frame": 20, "note": "Keep"},
        {"id": "two", "asset_id": aid, "moment_id": aid, "start_frame": 4, "end_frame": 22, "note": "Repeat"}]}]
    assert client.put(f"/api/projects/{pid}/board", json={"revision": 0, "sections": board}).status_code == 200
    saved = db.one("SELECT board,revision FROM projects WHERE id=?", (pid,))
    revisions = db.rows("SELECT * FROM revisions WHERE project_id=?", (pid,))
    original = (config.asset_dir(aid) / "original.mp4").read_bytes()
    env = {**os.environ, "STORYROOM_DATA": str(config.DATA), "GEMINI_API_KEY": "", "GOOGLE_API_KEY": "",
           "STORYROOM_PRICING_CONFIRMED": "false", "STORYROOM_SPEND_LIMIT": "0"}
    logs = (tmp_path / "worker.log").open("w+")
    processes = []

    def start(extra=None):
        p = subprocess.Popen([sys.executable, "-m", "server.worker"], cwd=ROOT,
                             env={**env, **(extra or {})}, stdout=logs, stderr=logs, start_new_session=True)
        processes.append(p)
        return p

    def queue():
        if kind == "render":
            response = client.post(f"/api/projects/{pid}/jobs/render", json={})
            assert response.status_code == 200
            return response.json()["job_id"], aid
        target = client.post("/api/projects", json={"name": "Pending", "brief": ""}).json()["id"]
        with clip.open("rb") as source:
            response = client.post(f"/api/projects/{target}/import", files={"file": ("generated.mp4", source, "video/mp4")})
        assert response.status_code == 200
        asset = response.json()["id"]
        return db.one("SELECT id FROM jobs WHERE project_id=?", (target,))["id"], asset

    def status(jid):
        return db.one("SELECT status FROM jobs WHERE id=?", (jid,))["status"]

    try:
        pending, _ = queue()
        worker = start()
        wait_for(lambda: status(pending) == "done")
        stop(worker)
        interrupted, target_aid = queue()
        # Hold exactly at the subprocess media boundary, avoiding a race with a
        # tiny fixture finishing before the test can terminate its worker group.
        wrapper_dir = tmp_path / "tools"
        wrapper_dir.mkdir()
        marker = tmp_path / "encoder-started"
        wrapper = wrapper_dir / "ffmpeg"
        wrapper.write_text(f"#!{sys.executable}\nimport pathlib, time, os, sys\npathlib.Path({str(marker)!r}).touch()\nwhile not pathlib.Path({str(tmp_path / 'release')!r}).exists(): time.sleep(.05)\nos.execv({shutil.which('ffmpeg')!r}, ['ffmpeg', *sys.argv[1:]])\n")
        wrapper.chmod(0o755)
        worker = start({"PATH": str(wrapper_dir) + os.pathsep + env["PATH"]})
        wait_for(marker.exists)
        assert status(interrupted) == "running"
        competitor = start()
        assert competitor.wait(timeout=10) != 0
        assert status(interrupted) == "running"
        logs.flush()
        assert "Another Storyroom worker" in (tmp_path / "worker.log").read_text()
        stop(worker)
        # An interrupted paid job is marked failed, never put back on the queue.
        paid = db.enqueue(pid, "analyze", {"asset_id": aid})
        db.execute("UPDATE jobs SET status='running' WHERE id=?", (paid,))
        worker = start()
        wait_for(lambda: status(interrupted) == "failed")
        assert status(paid) == "failed"
        if kind == "normalize":
            assert db.one("SELECT status,error FROM assets WHERE id=?", (target_aid,))["status"] == "failed"
        retry = client.post(f"/api/jobs/{interrupted}/retry").json()["job_id"]
        wait_for(lambda: status(retry) == "done")
        assert status(paid) == "failed"
        assert db.one("SELECT COUNT(*) AS n FROM usage")["n"] == 0
        assert db.one("SELECT board,revision FROM projects WHERE id=?", (pid,)) == saved
        assert db.rows("SELECT * FROM revisions WHERE project_id=?", (pid,)) == revisions
        assert db.one("SELECT status FROM assets WHERE id=?", (aid,))["status"] == "ready"
        assert (config.asset_dir(aid) / "original.mp4").read_bytes() == original
        if kind == "normalize":
            assert db.one("SELECT status FROM assets WHERE id=?", (target_aid,))["status"] == "ready"
            assert db.one("SELECT COUNT(*) AS n FROM moments WHERE asset_id=?", (target_aid,))["n"] == 1
        else:
            assert client.get(f"/api/jobs/{retry}/download").status_code == 200
    finally:
        for process in processes:
            if process.poll() is None:
                stop(process)
        logs.close()
