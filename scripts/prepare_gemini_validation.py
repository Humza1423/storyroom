"""Download eight reviewed-license sources and prepare opaque bounded test inputs.

No cloud model calls, database changes, or indexing. Human labels are frozen
separately after contact-sheet inspection and before search evaluation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

CC = "https://creativecommons.org/licenses/"
COMMONS = "https://commons.wikimedia.org/wiki/File:"
UPLOAD = "https://upload.wikimedia.org/wikipedia/commons/"
DVIDS = "https://www.dvidshub.net/about/copyright"
SOURCES = [
    {
        "id": "f01",
        "title": "Football Tennis",
        "author": "PK17 Football (PredatorKnuckles17) UK HD",
        "collection": "wikimedia_commons",
        "page": COMMONS + "Football_Tennis.webm",
        "url": UPLOAD + "8/87/Football_Tennis.webm",
        "license": "CC BY 3.0",
        "license_url": CC + "by/3.0/",
        "start": 0,
        "seconds": 30,
    },
    {
        "id": "f02",
        "title": "Badmington Competition EuroGames 2 2023 in Wankdork, Bern",
        "author": "Hyruspex",
        "collection": "wikimedia_commons",
        "page": COMMONS
        + "Badmington_Competition_EuroGames_2_2023_in_Wankdork,_Bern.webm",
        "url": UPLOAD
        + "4/40/Badmington_Competition_EuroGames_2_2023_in_Wankdork%2C_Bern.webm",
        "license": "CC BY-SA 4.0",
        "license_url": CC + "by-sa/4.0/",
        "start": 0,
        "seconds": 30,
    },
    {
        "id": "f03",
        "title": "Follow Me Fitness Normal Base Push-Up",
        "author": "Cpl. David Delgadillo / US Marine Corps",
        "collection": "dvids",
        "page": "https://www.dvidshub.net/video/590723/follow-me-fitness-normal-base-push-up",
        "url": "https://d34w7g4gy10iej.cloudfront.net/video/1803/DOD_105434180/DOD_105434180-1024x576-1769k.mp4",
        "license": "US government public domain",
        "license_url": DVIDS,
        "start": 8,
        "seconds": 30,
    },
    {
        "id": "f04",
        "title": "Spangdahlem Blue Page 250902 Volleyball Tournament",
        "author": "Airman 1st Class Jessica Mun / US Air Force",
        "collection": "dvids",
        "page": "https://www.dvidshub.net/video/975720/spangdahlem-blue-page-250902-volleyball-tournament",
        "url": "https://d34w7g4gy10iej.cloudfront.net/video/2509/DOD_111269784/DOD_111269784-1920x1080-9000k.mp4",
        "license": "US government public domain",
        "license_url": DVIDS,
        "start": 0,
        "seconds": 15,
    },
    {
        "id": "f05",
        "title": "Horses running in a pasture",
        "author": "Field of Dreams",
        "collection": "wikimedia_commons",
        "page": COMMONS + "Horses_running_in_a_pasture.webm",
        "url": UPLOAD + "a/af/Horses_running_in_a_pasture.webm",
        "license": "CC BY 3.0",
        "license_url": CC + "by/3.0/",
        "start": 0,
        "seconds": 30,
    },
    {
        "id": "f06",
        "title": "Noodle cooking 1 2020-05-18",
        "author": "FASTILY",
        "collection": "wikimedia_commons",
        "page": COMMONS + "Noodle_cooking_1_2020-05-18.webm",
        "url": UPLOAD + "6/6e/Noodle_cooking_1_2020-05-18.webm",
        "license": "CC BY-SA 4.0",
        "license_url": CC + "by-sa/4.0/",
        "start": 0,
        "seconds": 20.334,
    },
    {
        "id": "f07",
        "title": "BIM badminton (Malaysian Sign Language)",
        "author": "PeaceSeekers",
        "collection": "wikimedia_commons",
        "page": COMMONS + "BIM_badminton.webm",
        "url": UPLOAD + "e/ed/BIM_badminton.webm",
        "license": "CC0 1.0",
        "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
        "start": 0,
        "seconds": 2.633,
    },
    {
        "id": "f08",
        "title": "PACE True Color rotating globe",
        "author": "NASA / Marit Jentoft-Nilsen (GST)",
        "collection": "nasa_svs",
        "page": "https://svs.gsfc.nasa.gov/31365/",
        "url": "https://svs.gsfc.nasa.gov/vis/a030000/a031300/a031365/pace_sfrefl_rotating_globe_1080p30.mp4",
        "license": "NASA media usage guidelines",
        "license_url": "https://www.nasa.gov/nasa-brand-center/images-and-media/",
        "start": 0,
        "seconds": 30,
    },
]


def run(*command):
    return subprocess.run(command, check=True, capture_output=True, text=True).stdout


def inspect(path):
    return json.loads(
        run(
            "ffprobe",
            "-v",
            "error",
            "-show_format",
            "-show_streams",
            "-of",
            "json",
            str(path),
        )
    )


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path("data/evaluation/gemini-fresh")
    )
    parser.add_argument("--only", choices=[row["id"] for row in SOURCES])
    args = parser.parse_args()
    root = args.root.resolve()
    for name in ("raw", "inputs", "contact"):
        (root / name).mkdir(parents=True, exist_ok=True)
    frozen = root / "answer-key-frozen-v1.json"
    if not frozen.exists():
        frozen.write_bytes(
            (
                Path(__file__).resolve().parents[1]
                / "tests/fixtures/gemini-fresh-answer-key-v1.json"
            ).read_bytes()
        )
    manifest = root / "provenance.json"
    records = (
        {row["id"]: row for row in json.loads(manifest.read_text())}
        if manifest.exists()
        else {}
    )
    for source in SOURCES:
        if args.only and source["id"] != args.only:
            continue
        source = dict(source)
        extension = ".webm" if ".webm" in source["url"] else ".mp4"
        raw = root / "raw" / (source["id"] + extension)
        if not raw.exists():
            temporary = raw.with_suffix(raw.suffix + ".part")
            run(
                "curl",
                "-fL",
                "--retry",
                "2",
                "--max-time",
                "180",
                "-o",
                str(temporary),
                source["url"],
            )
            inspect(temporary)
            temporary.replace(raw)
        output = root / "inputs" / (source["id"] + ".mp4")
        command = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-y",
            "-ss",
            str(source["start"]),
            "-i",
            str(raw),
            "-t",
            str(source["seconds"]),
            "-map",
            "0:v:0",
            "-map",
            "0:a:0?",
            "-vf",
            "scale=1280:720:force_original_aspect_ratio=decrease:force_divisible_by=2,fps=30,setsar=1",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "22",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            str(output),
        ]
        if not output.exists():
            run(*command)
        sheet = root / "contact" / (source["id"] + ".jpg")
        run(
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(output),
            "-vf",
            "fps=1,scale=240:-1,tile=6x6",
            "-frames:v",
            "1",
            str(sheet),
        )
        source.update(
            access_date=str(datetime.now(UTC).date()),
            original_bytes=raw.stat().st_size,
            original_sha256=digest(raw),
            input_sha256=digest(output),
            original_probe=inspect(raw),
            input_probe=inspect(output),
            conversion=command,
            input_file=str(output.relative_to(root)),
        )
        records[source["id"]] = source
        manifest.write_text(json.dumps(list(records.values()), indent=2) + "\n")
        print(f"{source['id']}: prepared {output}", flush=True)


if __name__ == "__main__":
    main()
