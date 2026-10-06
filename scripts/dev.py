"""Run API, worker, and UI together. Ctrl-C stops all three."""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    os.chdir(ROOT)
    commands = [
        [
            sys.executable,
            "-m",
            "uvicorn",
            "server.app:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8765",
        ],
        [sys.executable, "-m", "server.worker"],
        ["npm", "run", "dev"],
    ]
    children = []
    try:
        for cmd in commands:
            children.append(subprocess.Popen(cmd, start_new_session=True))
        print(
            "\nStoryroom: http://127.0.0.1:5173\nCtrl-C stops the workspace.",
            flush=True,
        )
        while all(p.poll() is None for p in children):
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        for p in children:
            try:
                os.killpg(p.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        for p in children:
            try:
                p.wait(5)
            except subprocess.TimeoutExpired:
                os.killpg(p.pid, signal.SIGKILL)
                p.wait()


if __name__ == "__main__":
    main()
