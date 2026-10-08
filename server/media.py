import json
import shutil
import subprocess
import time
from pathlib import Path
from . import config


class Cancelled(Exception):
    pass


def run(args, cancelled=lambda: False):
    # Never invoke a shell with user-supplied filenames.
    import tempfile

    with tempfile.TemporaryFile() as stderr:
        process = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=stderr)
        started = time.monotonic()
        try:
            while process.poll() is None:
                if cancelled():
                    raise Cancelled("Cancelled")
                if time.monotonic() - started > 1200:
                    raise ValueError("Media operation timed out after 20 minutes")
                time.sleep(0.1)
            if process.returncode:
                stderr.seek(0)
                raise ValueError(
                    "Media processing failed: "
                    + stderr.read().decode(errors="replace")[-1200:]
                )
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


class InspectionUnavailable(ValueError):
    pass


def probe(path):
    if not shutil.which("ffprobe"):
        raise InspectionUnavailable(
            "Install FFmpeg (including ffprobe) before importing footage."
        )
    try:
        r = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_streams",
                "-show_format",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            timeout=30,
            check=True,
        )
        data = json.loads(r.stdout)
        v = next(s for s in data["streams"] if s["codec_type"] == "video")
        duration = float(v.get("duration") or data["format"]["duration"])
        if not 0 < duration <= config.MAX_SECONDS:
            raise ValueError("Clip must have a valid duration of at most 15 minutes.")
        return {
            "duration": duration,
            "frames": round(duration * 30),
            "width": v["width"],
            "height": v["height"],
            "has_audio": any(s["codec_type"] == "audio" for s in data["streams"]),
            "codec": v["codec_name"],
            "transfer": v.get("color_transfer"),
            "pix_fmt": v.get("pix_fmt"),
            "format": data["format"].get("format_name", ""),
        }
    except subprocess.TimeoutExpired as exc:
        raise InspectionUnavailable(
            "Media inspection timed out. Check the local server before retrying."
        ) from exc
    except (subprocess.SubprocessError, KeyError, StopIteration, json.JSONDecodeError):
        raise ValueError(
            "Cannot read this video. Use an intact H.264 MP4 file."
        ) from None


def validate(info):
    if info["codec"] != "h264" or "mp4" not in info["format"]:
        raise ValueError("Version 1 supports H.264 MP4 footage only.")
    if (
        max(info["width"], info["height"]) > 1920
        or min(info["width"], info["height"]) > 1080
    ):
        raise ValueError("Version 1 supports up to 1080p, including portrait footage.")
    if info["transfer"] in ("smpte2084", "arib-std-b67") or "10" in (
        info["pix_fmt"] or ""
    ):
        raise ValueError(
            "HDR / 10-bit footage is not supported yet. Convert to SDR H.264 first."
        )


def encode(source, dest, proxy=False, cancelled=lambda: False):
    vf = "fps=30,setsar=1"
    if proxy:
        vf += (
            ",scale=1280:720:force_original_aspect_ratio=decrease:force_divisible_by=2"
        )
    temp = dest.with_name(dest.stem + ".partial.mp4")
    run(
        [
            "ffmpeg",
            "-nostdin",
            "-y",
            "-v",
            "error",
            "-i",
            str(source),
            "-map",
            "0:v:0",
            "-map",
            "0:a:0?",
            "-vf",
            vf,
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "25" if proxy else "18",
            "-pix_fmt",
            "yuv420p",
            "-threads",
            "2",
            "-c:a",
            "aac",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-af",
            "aresample=async=1:first_pts=0",
            "-movflags",
            "+faststart",
            str(temp),
        ],
        cancelled,
    )
    temp.replace(dest)


def normalize(asset, cancelled=lambda: False):
    folder = config.asset_dir(asset["id"])
    encode(folder / "original.mp4", folder / "edit.mp4", cancelled=cancelled)
    encode(folder / "edit.mp4", folder / "proxy.mp4", proxy=True, cancelled=cancelled)
    thumbnail(folder / "proxy.mp4", folder / "thumb.jpg", cancelled)
    return probe(folder / "edit.mp4")


def thumbnail(source, dest, cancelled=lambda: False):
    run(
        [
            "ffmpeg",
            "-nostdin",
            "-y",
            "-v",
            "error",
            "-i",
            str(source),
            "-frames:v",
            "1",
            "-vf",
            "scale=480:-2",
            "-threads",
            "2",
            str(dest),
        ],
        cancelled,
    )


def chunk(source, dest, start, duration, cancelled=lambda: False):
    run(
        [
            "ffmpeg",
            "-nostdin",
            "-y",
            "-v",
            "error",
            "-ss",
            str(start),
            "-i",
            str(source),
            "-t",
            str(duration),
            "-an",
            "-vf",
            "scale=640:360:force_original_aspect_ratio=decrease:force_divisible_by=2,fps=2",
            "-c:v",
            "libx264",
            "-crf",
            "26",
            "-threads",
            "2",
            str(dest),
        ],
        cancelled,
    )


def render(
    board, assets, dest, cancelled=lambda: False, report=lambda fraction, message: None
):
    import tempfile

    clips = [s for section in board for s in section["selections"]]
    if not clips:
        raise ValueError("Choose at least one clip before rendering.")
    with tempfile.TemporaryDirectory(dir=config.DATA) as tmp:
        parts = []
        for i, clip in enumerate(clips):
            report(i / len(clips) * 0.9, f"Rendering clip {i + 1}/{len(clips)}")
            asset = assets[clip["asset_id"]]
            source = config.asset_dir(asset["id"]) / "edit.mp4"
            if not source.exists():
                raise ValueError(
                    f"Editing media is missing for {asset['name']}. Retry its media job."
                )
            part = Path(tmp) / f"part{i:04}.mp4"
            length = (clip["end_frame"] - clip["start_frame"]) / 30
            args = [
                "ffmpeg",
                "-nostdin",
                "-y",
                "-v",
                "error",
                "-ss",
                str(clip["start_frame"] / 30),
                "-i",
                str(source),
            ]
            if not asset["has_audio"]:
                args += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
            args += [
                "-map",
                "0:v:0",
                "-map",
                "0:a:0" if asset["has_audio"] else "1:a:0",
                "-t",
                str(length),
                "-vf",
                "scale=1280:720:force_original_aspect_ratio=decrease:force_divisible_by=2,pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30",
                "-af",
                "apad",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "23",
                "-threads",
                "2",
                "-c:a",
                "aac",
                "-ar",
                "48000",
                "-ac",
                "2",
                str(part),
            ]
            run(args, cancelled)
            parts.append(part)
        report(0.95, "Joining rendered clips")
        listing = Path(tmp) / "parts.txt"
        # Generated basenames only; no user text enters the concat manifest.
        listing.write_text("\n".join(f"file '{p.name}'" for p in parts))
        partial = dest.with_suffix(".partial.mp4")
        run(
            [
                "ffmpeg",
                "-nostdin",
                "-y",
                "-v",
                "error",
                "-f",
                "concat",
                "-safe",
                "1",
                "-i",
                str(listing),
                "-c",
                "copy",
                "-movflags",
                "+faststart",
                str(partial),
            ],
            cancelled,
        )
        partial.replace(dest)
