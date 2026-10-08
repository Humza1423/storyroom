"""Launcher boundaries without touching a development process or data directory."""
import importlib.util
from pathlib import Path
import socket

import pytest

spec = importlib.util.spec_from_file_location("dev", Path(__file__).parents[1] / "scripts/dev.py")
dev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dev)


def test_occupied_port():
    with socket.socket() as owner:
        owner.bind(("127.0.0.1", 0))
        with pytest.raises(RuntimeError, match="occupied"):
            dev.check_ports({"STORYROOM_API_PORT": str(owner.getsockname()[1])})


def test_missing_media_tool_is_actionable(monkeypatch, tmp_path):
    original = dev.shutil.which
    monkeypatch.setattr(dev.shutil, "which", lambda command, **kwargs: None if command == "ffprobe" else original(command, **kwargs))
    with pytest.raises(RuntimeError, match="Missing ffprobe.*brew install ffmpeg"):
        dev.preflight({"STORYROOM_DATA": str(tmp_path / "data")})


def test_owned_stack_cleanup_and_development_sentinel(tmp_path):
    import os
    import subprocess
    import sys
    import fcntl
    sentinel = tmp_path / "development"
    sentinel.mkdir()
    (sentinel / "project.txt").write_text("saved choices")
    with socket.socket() as a, socket.socket() as b:
        a.bind(("127.0.0.1", 0))
        b.bind(("127.0.0.1", 0))
        ports = [str(a.getsockname()[1]), str(b.getsockname()[1])]
    env = {**os.environ, "STORYROOM_DATA": str(tmp_path / "owned"),
           "STORYROOM_API_PORT": ports[0], "STORYROOM_UI_PORT": ports[1],
           "GEMINI_API_KEY": "", "GOOGLE_API_KEY": "", "STORYROOM_PRICING_CONFIRMED": "false", "STORYROOM_SPEND_LIMIT": "0"}
    result = subprocess.run([sys.executable, "-c",
        "import os,sys; from scripts.dev import run_stack; sys.exit(run_stack(os.environ,[sys.executable,'-c','raise SystemExit(7)']))"],
        cwd=dev.ROOT, env=env, capture_output=True, text=True, timeout=60)
    assert result.returncode == 7, result.stdout + result.stderr
    assert "Storyroom ready" in result.stdout
    dev.check_ports(env)
    with open(tmp_path / "owned/worker.lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    assert list(sentinel.iterdir()) == [sentinel / "project.txt"]
    assert (sentinel / "project.txt").read_text() == "saved choices"


def test_failed_child_is_named_and_exits_nonzero(tmp_path):
    import os
    import sqlite3
    import subprocess
    import sys
    data = tmp_path / "future"
    data.mkdir()
    with sqlite3.connect(data / "storyroom.sqlite") as c:
        c.execute("CREATE TABLE schema_versions(version INTEGER PRIMARY KEY)")
        c.executemany("INSERT INTO schema_versions VALUES(?)", [(1,), (2,)])
    with socket.socket() as a, socket.socket() as b:
        a.bind(("127.0.0.1", 0))
        b.bind(("127.0.0.1", 0))
        ports = [str(a.getsockname()[1]), str(b.getsockname()[1])]
    env = {**os.environ, "STORYROOM_DATA": str(data), "STORYROOM_API_PORT": ports[0],
           "STORYROOM_UI_PORT": ports[1], "GEMINI_API_KEY": "", "GOOGLE_API_KEY": "",
           "STORYROOM_PRICING_CONFIRMED": "false", "STORYROOM_SPEND_LIMIT": "0"}
    result = subprocess.run([sys.executable, "scripts/dev.py"], cwd=dev.ROOT, env=env,
                            text=True, capture_output=True, timeout=60)
    assert result.returncode == 1
    assert "Startup failed:" in result.stderr
    assert "exited" in result.stderr
    assert "newer than supported" in result.stderr
    assert "Storyroom ready" not in result.stdout
    dev.check_ports(env)
