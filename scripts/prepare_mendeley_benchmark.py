"""Build an opaque, normalized, subject-split local search test set.

Input is the 50-file sample extracted by inspect_mendeley_zip.py. The resulting
development/holdout folders contain opaque names, stripped container metadata,
and normalized SDR H.264 inputs. Source labels and hashes stay in the ignored
local provenance manifest and are never copied into filenames or media tags.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

DATASET_PAGE = "https://data.mendeley.com/datasets/kgbb3yn47p/3"
DOI = "10.17632/kgbb3yn47p.3"
LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"
ARCHIVE_URL = (
    "https://data.mendeley.com/public-files/datasets/kgbb3yn47p/files/"
    "a31fa913-6f29-4c31-b1a6-414a718eebf4/file_downloaded"
)
AUTHORS = [
    "Duddela Sai Prashanth",
    "Priya Kamath",
    "Rakshith Bhandary",
    "S Ashlesh Pai",
    "Pratham PN",
    "Advith P",
    "Abhishek Mashetty",
]
EXPECTED_EXERCISES = {"abs", "back", "bicep_curl", "push_up", "squat"}
NAME = re.compile(
    r"subject_(?P<subject>\d{3})_(?P<exercise>[a-z_]+)_"
    r"(?P<form>good|bad)_(?P<view>side|front|diagonal)\.mp4$"
)


def probe(path):
    raw = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    data = json.loads(raw)
    video = next((row for row in data["streams"] if row["codec_type"] == "video"), None)
    audio = [row for row in data["streams"] if row["codec_type"] == "audio"]
    if not video:
        raise ValueError(f"No video stream found in {path.name}")
    return {
        "duration_sec": float(data.get("format", {}).get("duration", 0)),
        "container": data.get("format", {}).get("format_name"),
        "video_codec": video.get("codec_name"),
        "width": video.get("width"),
        "height": video.get("height"),
        "pixel_format": video.get("pix_fmt"),
        "frame_rate": video.get("avg_frame_rate"),
        "transfer": video.get("color_transfer"),
        "audio": [
            {
                "codec": row.get("codec_name"),
                "channels": row.get("channels"),
                "sample_rate": row.get("sample_rate"),
            }
            for row in audio
        ],
    }


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def convert(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(
            f"Refusing to overwrite existing evaluation input: {destination}"
        )
    temporary = destination.with_name(destination.stem + ".partial.mp4")
    try:
        subprocess.run(
            [
                "ffmpeg", "-nostdin", "-y", "-v", "error", "-i", str(source),
                "-map", "0:v:0", "-map", "0:a:0?", "-map_metadata", "-1",
                "-map_chapters", "-1", "-vf",
                "scale=w='min(1920,iw)':h='min(1080,ih)':force_original_aspect_ratio=decrease:force_divisible_by=2,fps=30",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "48000",
                "-ac", "2", "-movflags", "+faststart", str(temporary),
            ],
            check=True,
        )
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-dir", type=Path,
        default=Path("data/evaluation/visual-search/mendeley-originals"),
    )
    parser.add_argument(
        "--output-dir", type=Path,
        default=Path("data/evaluation/visual-search/mendeley"),
    )
    args = parser.parse_args()
    files = sorted(args.source_dir.glob("*.mp4"))
    if len(files) != 50:
        raise SystemExit(f"Expected exactly 50 extracted videos; found {len(files)}.")

    categories = {exercise: 0 for exercise in EXPECTED_EXERCISES}
    subjects = set()
    manifest_rows = []
    for source in files:
        match = NAME.search(source.name)
        if not match:
            raise SystemExit(f"Unexpected source filename: {source.name}")
        label = match.groupdict()
        subject = int(label["subject"])
        exercise = label["exercise"]
        if exercise not in EXPECTED_EXERCISES or not 1 <= subject <= 10:
            raise SystemExit(f"Source outside chosen sample: {source.name}")
        categories[exercise] += 1
        subjects.add(subject)
        source_hash = sha256_file(source)
        if source.stat().st_size > 200_000_000:
            raise SystemExit(f"Unexpectedly large video: {source.name}")
        source_media = probe(source)
        transfer = (source_media["transfer"] or "").lower()
        if "smpte2084" in transfer or "arib-std-b67" in transfer or "10" in (source_media["pixel_format"] or ""):
            raise SystemExit(f"HDR/10-bit file requires a separately reviewed conversion: {source.name}")

        group = "development" if subject <= 5 else "test"
        asset_key = hashlib.sha256(
            f"{DOI}:{source.name}:{source_hash}".encode()
        ).hexdigest()[:16]
        destination = args.output_dir / "inputs" / group / f"clip-{asset_key}.mp4"
        convert(source, destination)
        output_media = probe(destination)
        output_hash = sha256_file(destination)
        if output_media["video_codec"] != "h264" or output_media["width"] > 1920 or output_media["height"] > 1080:
            raise ValueError(f"Converted input violates Storyroom test bounds: {destination.name}")
        if abs(output_media["duration_sec"] - source_media["duration_sec"]) > 1 / 30:
            raise ValueError(f"Conversion changed duration by more than one 30-fps frame: {source.name}")

        manifest_rows.append(
            {
                "asset_key": asset_key,
                "category": exercise,
                "footage_group": f"participant-{subject:03d}",
                "split": group,
                "form_label": label["form"],
                "view_label": label["view"],
                "source_title": "A Multi-View Raw Video Dataset of Seven Fitness Exercises with Good/Bad Form Labels",
                "source_author": AUTHORS,
                "source_page": DATASET_PAGE,
                "permanent_identifier": f"https://doi.org/{DOI}",
                "source_archive_url": ARCHIVE_URL,
                "archive_member": f"Dataset Exercise-wise/{exercise}/{label['form']}/{label['view']}/{source.name}",
                "license": "CC BY 4.0",
                "license_url": LICENSE_URL,
                "access_date": datetime.now(UTC).date().isoformat(),
                "original_path": str(source),
                "original_bytes": source.stat().st_size,
                "original_sha256": source_hash,
                "original_media": source_media,
                "input_path": str(destination),
                "input_bytes": destination.stat().st_size,
                "input_sha256": output_hash,
                "input_media": output_media,
                "conversion": "FFmpeg to SDR H.264, max 1920x1080, 30 fps, yuv420p; AAC audio retained if present; global/chapter metadata stripped; app embedding chunks are separately muted.",
                "cloud_analysis_approved": False,
                "action_start_sec": None,
                "action_end_sec": None,
                "label_review": "pending visual review",
            }
        )
        print(f"Prepared {asset_key} · {exercise} · {group} · {output_media['duration_sec']:.1f}s")

    if set(categories) != EXPECTED_EXERCISES or any(count != 10 for count in categories.values()):
        raise SystemExit(f"Expected 10 videos in every exercise class; got {categories}")
    if subjects != set(range(1, 11)):
        raise SystemExit(f"Expected participants 001–010; got {sorted(subjects)}")
    manifest = {
        "created_at": datetime.now(UTC).isoformat(),
        "dataset_page": DATASET_PAGE,
        "dataset_doi": DOI,
        "license": "CC BY 4.0",
        "purpose": "Local visual-search quality pilot; author/form/view labels are kept out of input names and container metadata.",
        "split_policy": "Participants 001–005 are development; 006–010 are held-out test. Every clip from a participant remains in one split.",
        "categories": categories,
        "videos": sorted(manifest_rows, key=lambda row: (row["split"], row["category"], row["asset_key"])),
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / "provenance.json"
    if output.exists():
        raise SystemExit(f"Refusing to overwrite existing manifest: {output}")
    output.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Wrote local provenance and answer-label inventory: {output}")


if __name__ == "__main__":
    main()
