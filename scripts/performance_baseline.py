"""Run one bounded, generated Storyroom media baseline in temporary storage."""

import json
import os
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from server import config, db
from server.app import app
from server.worker import once


def generated_clip(path):
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=640x360:rate=30:duration=2",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=880:sample_rate=48000:duration=2",
            "-c:v",
            "libx264",
            "-threads",
            "2",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(path),
        ],
        check=True,
        timeout=30,
    )


def summarize_job(project_id, kind):
    row = db.one(
        "SELECT result FROM jobs WHERE project_id=? AND kind=? ORDER BY created DESC LIMIT 1",
        (project_id, kind),
    )
    if not row or not row["result"]:
        raise RuntimeError(f"No completed {kind} job result was saved")
    result = json.loads(row["result"])
    if not result.get("diagnostics"):
        raise RuntimeError(f"The {kind} job did not save media diagnostics")
    return result


def run_baseline():
    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            raise RuntimeError(
                f"Install FFmpeg, including {tool}, before running this baseline"
            )

    original_data = config.DATA
    try:
        with tempfile.TemporaryDirectory(prefix="storyroom-performance-") as root:
            root = Path(root)
            config.DATA = root / "data"
            db.init()
            source = root / "generated.mp4"
            generated_clip(source)

            with TestClient(app, headers={"X-Storyroom": "local"}) as client:
                project = client.post(
                    "/api/projects", json={"name": "Generated performance baseline"}
                ).json()["id"]
                with source.open("rb") as video:
                    imported = client.post(
                        f"/api/projects/{project}/import",
                        files={"file": ("generated.mp4", video, "video/mp4")},
                    )
                imported.raise_for_status()
                asset = imported.json()["id"]
                if not once():
                    raise RuntimeError("The normalization job was not queued")
                normalized = summarize_job(project, "normalize")

                sections = [
                    {
                        "id": "generated-section",
                        "title": "Three short cuts",
                        "purpose": "",
                        "selections": [
                            {
                                "id": f"cut-{index}",
                                "asset_id": asset,
                                "moment_id": asset,
                                "start_frame": start,
                                "end_frame": end,
                                "note": "",
                            }
                            for index, (start, end) in enumerate(
                                ((0, 30), (15, 45), (30, 60))
                            )
                        ],
                    }
                ]
                saved = client.put(
                    f"/api/projects/{project}/board",
                    json={"revision": 0, "sections": sections},
                )
                saved.raise_for_status()
                queued = client.post(
                    f"/api/projects/{project}/jobs/render", json={"query": ""}
                )
                queued.raise_for_status()
                render_job = queued.json()["job_id"]
                if not once():
                    raise RuntimeError("The render job was not queued")
                rendered = summarize_job(project, "render")
                if rendered["url"] != f"/api/jobs/{render_job}/download":
                    raise RuntimeError(
                        "The rendered result did not preserve its download URL"
                    )

            version = subprocess.run(
                ["ffmpeg", "-version"], capture_output=True, text=True, check=True
            ).stdout.splitlines()[0]
            model = "unknown"
            if platform.system() == "Darwin":
                probe = subprocess.run(
                    ["sysctl", "-n", "hw.model"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if probe.returncode == 0:
                    model = probe.stdout.strip()
            return {
                "machine": {
                    "system": platform.system(),
                    "os_version": platform.mac_ver()[0] or platform.release(),
                    "architecture": platform.machine(),
                    "model": model,
                    "cpu_count": os.cpu_count(),
                },
                "ffmpeg": version,
                "fixture": {
                    "generated_video": "640x360, 30 fps, 2 seconds, H.264",
                    "generated_audio": "880 Hz sine, 48 kHz, AAC",
                    "assembly": "three 30-frame placements with overlapping ranges",
                    "storage": "temporary and removed after report generation",
                },
                "normalization": normalized["diagnostics"],
                "render": rendered["diagnostics"],
            }
    finally:
        config.DATA = original_data


if __name__ == "__main__":
    print(json.dumps(run_baseline(), indent=2))
