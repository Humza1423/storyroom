import subprocess
import pytest
from fastapi.testclient import TestClient
from server import config, db
from server.app import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA", tmp_path / "data")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("GOOGLE_API_KEY", "")
    monkeypatch.setattr(config, "PRICING_CONFIRMED", False)
    # Fake-provider ledger tests need a finite allowance, independent of CI's
    # zero-budget subprocess environment. Real clients remain disabled above.
    monkeypatch.setattr(config, "SPEND_LIMIT", 45)
    with TestClient(app, headers={"X-Storyroom": "local"}) as c:
        yield c


@pytest.fixture
def clip(tmp_path):
    path = tmp_path / "source.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-y",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=320x180:rate=24:duration=1",
            "-c:v",
            "libx264",
            "-threads",
            "2",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ],
        check=True,
    )
    return path


def create_ready(client, clip):
    from server.worker import once

    pid = client.post(
        "/api/projects",
        json={"name": "Test project", "brief": "Show training progress"},
    ).json()["id"]
    with clip.open("rb") as f:
        response = client.post(
            f"/api/projects/{pid}/import",
            files={"file": ("sample.mp4", f, "video/mp4")},
        )
    assert response.status_code == 200, response.text
    aid = response.json()["id"]
    assert once()
    assert db.one("SELECT status FROM assets WHERE id=?", (aid,))["status"] == "ready"
    return pid, aid
