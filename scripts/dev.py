"""Own API, worker and UI processes; wait for readiness and stop only our groups."""

import os
import errno
import importlib.util
import shutil
import tempfile
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def preflight(env):
    if sys.version_info[:2] != (3, 12):
        raise RuntimeError(
            "Python 3.12 required. Recreate .venv using the README setup."
        )
    for module in (
        "fastapi",
        "uvicorn",
        "dotenv",
        "httpx",
        "google.genai",
        "opentimelineio",
        "numpy",
        "multipart",
    ):
        try:
            found = importlib.util.find_spec(module)
        except ModuleNotFoundError:
            found = None
        if found is None:
            raise RuntimeError(
                f"Missing Python dependency {module}. Run the locked install from README."
            )
    for command in ("node", "npm", "ffmpeg", "ffprobe"):
        if not shutil.which(command, path=env.get("PATH")):
            remedy = (
                "brew install ffmpeg"
                if command in ("ffmpeg", "ffprobe")
                else "Install Node 22+ and npm"
            )
            raise RuntimeError(f"Missing {command}. {remedy}.")
    node = subprocess.run(
        ["node", "--version"], env=env, text=True, capture_output=True, check=True
    )
    if int(node.stdout.strip().lstrip("v").split(".")[0]) < 22:
        raise RuntimeError(
            "Node 22+ required. Install a supported Node release, then run npm ci."
        )
    if not (ROOT / "node_modules/vite/bin/vite.js").is_file():
        raise RuntimeError(
            "Frontend dependencies missing. Run npm ci in the repository."
        )
    data = Path(env.get("STORYROOM_DATA", ROOT / "data"))
    try:
        data.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryFile(dir=data):
            pass
    except OSError as exc:
        raise RuntimeError(
            "Data directory is not writable. Set STORYROOM_DATA to a writable directory."
        ) from exc


def check_ports(env):
    for key, default in (("STORYROOM_API_PORT", "8765"), ("STORYROOM_UI_PORT", "5173")):
        port = int(env.get(key, default))
        with socket.socket() as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
            except OSError as exc:
                if exc.errno != errno.EADDRINUSE:
                    raise RuntimeError(
                        f"Cannot bind loopback port {port}: {exc}"
                    ) from exc
                raise RuntimeError(
                    f"Port {port} is occupied. Stop its owner or set {key} to a free port."
                ) from exc


def handle_shutdown(_signum, _frame):
    raise KeyboardInterrupt


def stop(children):
    for _, child in children:
        try:
            os.killpg(child.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    for _, child in children:
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait()


def run_stack(env, test_command=None):
    env = dict(env)
    api_port = env.get("STORYROOM_API_PORT", "8765")
    ui_port = env.get("STORYROOM_UI_PORT", "5173")
    children = []
    try:
        check_ports(env)
        preflight(env)
        commands = [
            (
                "API",
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "server.app:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    api_port,
                ],
            ),
            ("worker", [sys.executable, "-m", "server.worker"]),
            ("frontend", ["npm", "run", "dev", "--", "--port", ui_port]),
        ]
        for name, command in commands:
            children.append(
                (
                    name,
                    subprocess.Popen(
                        command, cwd=ROOT, env=env, start_new_session=True
                    ),
                )
            )
        pending = {
            f"http://127.0.0.1:{api_port}/api/status",
            f"http://127.0.0.1:{ui_port}",
        }
        deadline = time.monotonic() + 45
        while pending:
            for name, child in children:
                if child.poll() is not None:
                    raise RuntimeError(
                        f"{name} exited ({child.returncode}); see its output above."
                    )
            for url in list(pending):
                try:
                    with urllib.request.urlopen(url, timeout=1) as response:
                        if response.status == 200:
                            pending.remove(url)
                except (OSError, TimeoutError):
                    pass
            if time.monotonic() > deadline:
                raise RuntimeError(f"Readiness timed out: {', '.join(pending)}")
            time.sleep(0.1)
        print(f"Storyroom ready: http://127.0.0.1:{ui_port}", flush=True)
        if test_command:
            child = subprocess.Popen(
                test_command, cwd=ROOT, env=env, start_new_session=True
            )
            children.append(("browser tests", child))
        while True:
            for name, child in children:
                if child.poll() is not None:
                    if name == "browser tests":
                        return child.returncode
                    raise RuntimeError(
                        f"{name} exited ({child.returncode}); see its output above."
                    )
            time.sleep(0.2)
    except KeyboardInterrupt:
        return 130
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
        print(f"Startup failed: {exc}", file=sys.stderr)
        return 1
    finally:
        stop(children)


if __name__ == "__main__":
    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")
    except ImportError:
        pass  # preflight provides the actionable missing-dependency message.
    signal.signal(signal.SIGTERM, handle_shutdown)
    sys.exit(run_stack(os.environ))
