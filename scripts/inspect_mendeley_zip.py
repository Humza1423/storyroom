"""List or selectively extract one public Mendeley ZIP using HTTP byte ranges.

This keeps the 3.1 GB exercise archive off a small development machine. Files
are data, never executable input. The default is read-only listing; extraction
requires exact member names and a bounded output directory outside Git.
"""

import argparse
import io
import json
import shutil
import urllib.request
import zipfile
import zlib
from pathlib import Path

URL = (
    "https://data.mendeley.com/public-files/datasets/kgbb3yn47p/files/"
    "a31fa913-6f29-4c31-b1a6-414a718eebf4/file_downloaded"
)
USER_AGENT = "curl/8.7.1"


class RemoteZip(io.RawIOBase):
    def __init__(self, url=URL):
        with urllib.request.urlopen(
            urllib.request.Request(
                url, method="HEAD", headers={"User-Agent": USER_AGENT}
            ),
            timeout=30,
        ) as response:
            self.url = response.url
            self.length = int(response.headers["Content-Length"])
            if response.headers.get("Accept-Ranges") != "bytes":
                raise RuntimeError("Dataset host does not support byte-range reads")
        self.position = 0
        self.cache = b""
        self.cache_start = -1

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=io.SEEK_SET):
        self.position = [offset, self.position + offset, self.length + offset][whence]
        if not 0 <= self.position <= self.length:
            raise ValueError("Seek outside archive")
        return self.position

    def read(self, size=-1):
        if size < 0:
            size = self.length - self.position
        size = min(size, 4 * 1024 * 1024)
        if size == 0 or self.position == self.length:
            return b""
        if not self.cache_start <= self.position < self.cache_start + len(self.cache):
            start = self.position
            end = min(self.length - 1, start + max(size, 1024 * 1024) - 1)
            request = urllib.request.Request(
                self.url,
                headers={"Range": f"bytes={start}-{end}", "User-Agent": USER_AGENT},
            )
            with urllib.request.urlopen(request, timeout=60) as response:
                if response.status != 206:
                    raise RuntimeError("Dataset host ignored byte range")
                self.cache = response.read()
                self.cache_start = start
        offset = self.position - self.cache_start
        result = self.cache[offset : offset + size]
        self.position += len(result)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extract", nargs="*", default=[])
    parser.add_argument(
        "--evaluation-sample",
        action="store_true",
        help="Extract 7 exercises for 3 distinct subjects/angles (21 clips)",
    )
    parser.add_argument(
        "--fitness-benchmark",
        action="store_true",
        help=(
            "Extract five exercise classes for ten subjects with varied form/view "
            "labels (50 clips); split later by subject to avoid leakage"
        ),
    )
    parser.add_argument("--output", type=Path, default=Path("data/evaluation/mendeley"))
    args = parser.parse_args()
    selected = list(args.extract)
    if args.evaluation_sample and args.fitness_benchmark:
        raise SystemExit("Choose only one of --evaluation-sample or --fitness-benchmark.")
    if args.evaluation_sample:
        for subject, quality, angle in (
            ("001", "good", "side"),
            ("002", "bad", "front"),
            ("003", "good", "diagonal"),
        ):
            for exercise in (
                "abs", "back", "bicep_curl", "push_up", "shoulder", "squat", "tricep"
            ):
                selected.append(
                    f"Dataset Exercise-wise/{exercise}/{quality}/{angle}/"
                    f"subject_{subject}_{exercise}_{quality}_{angle}.mp4"
                )
    if args.fitness_benchmark:
        for exercise in ("abs", "back", "bicep_curl", "push_up", "squat"):
            for subject in range(1, 11):
                quality = "good" if subject % 2 else "bad"
                angle = ("side", "front", "diagonal")[(subject - 1) % 3]
                selected.append(
                    f"Dataset Exercise-wise/{exercise}/{quality}/{angle}/"
                    f"subject_{subject:03d}_{exercise}_{quality}_{angle}.mp4"
                )
    with zipfile.ZipFile(RemoteZip()) as archive:
        members = archive.infolist()
        print(
            json.dumps(
                {"archive_bytes": archive.fp.length, "member_count": len(members)}
            )
        )
        if not selected:
            for member in members:
                print(json.dumps({"name": member.filename, "bytes": member.file_size}))
            return
        by_name = {member.filename: member for member in members}
        for name in selected:
            member = by_name.get(name)
            if member is None or member.is_dir() or not name.lower().endswith(".mp4"):
                raise ValueError(f"Not an exact MP4 member: {name}")
            if member.file_size > 200_000_000:
                raise ValueError(f"Member exceeds 200 MB safety limit: {name}")
            target = args.output / Path(name).name
            args.output.mkdir(parents=True, exist_ok=True)
            if target.exists():
                crc = 0
                with target.open("rb") as existing:
                    for block in iter(lambda: existing.read(1024 * 1024), b""):
                        crc = zlib.crc32(block, crc)
                if target.stat().st_size != member.file_size or crc != member.CRC:
                    raise FileExistsError(
                        f"Existing file differs from archive: {target}"
                    )
                print(json.dumps({"verified_existing": str(target)}))
                continue
            with archive.open(member) as source, target.open("xb") as dest:
                shutil.copyfileobj(source, dest, 1024 * 1024)
            print(
                json.dumps({"extracted": str(target), "bytes": target.stat().st_size})
            )


if __name__ == "__main__":
    main()
