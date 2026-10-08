"""Own an isolated browser stack and delete only our TemporaryDirectory."""
import os
from pathlib import Path
import subprocess
import sys
import sqlite3
import signal
import tempfile

from dev import ROOT, run_stack


def main():
    with tempfile.TemporaryDirectory(prefix="storyroom-e2e-") as directory:
        root = Path(directory)
        env = {**os.environ, "STORYROOM_DATA": str(root / "data"),
               "GEMINI_API_KEY": "", "GOOGLE_API_KEY": "",
               "STORYROOM_PRICING_CONFIRMED": "false", "STORYROOM_SPEND_LIMIT": "0",
               "STORYROOM_API_PORT": os.getenv("STORYROOM_TEST_API_PORT", "18765"),
               "STORYROOM_UI_PORT": os.getenv("STORYROOM_TEST_UI_PORT", "15173"),
               "STORYROOM_FIXTURES": str(root / "fixtures")}
        (root / "fixtures").mkdir()
        for index, color in enumerate(["red", "green", "blue"]):
            subprocess.run(["ffmpeg", "-nostdin", "-y", "-v", "error", "-f", "lavfi",
                            "-i", f"color=c={color}:size=320x180:rate=30:duration=2",
                            "-c:v", "libx264", "-threads", "2", "-pix_fmt", "yuv420p",
                            str(root / "fixtures" / f"clip-{index}.mp4")], check=True)
        env["STORYROOM_TEST_URL"] = f"http://127.0.0.1:{env['STORYROOM_UI_PORT']}"
        # An inherited development root is deliberately never used or cleaned.
        assert Path(env["STORYROOM_DATA"]).parent == root
        assert env["STORYROOM_DATA"] != os.environ.get("STORYROOM_DATA")
        print(f"Browser test data (owned): {env['STORYROOM_DATA']}", flush=True)
        result = run_stack(env, ["npx", "playwright", "test", *sys.argv[1:]])
        database = root / "data" / "storyroom.sqlite"
        if database.exists():
            with sqlite3.connect(database) as conn:
                assert conn.execute("SELECT COUNT(*) FROM usage").fetchone()[0] == 0
        return result


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    sys.exit(main())
