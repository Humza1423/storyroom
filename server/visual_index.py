"""Cheap temporal proposals; video embeddings supply meaning separately.

Visual change is not an action label. These boundaries are editable candidates,
not ground truth, especially when actions flow without a pause or shot cut.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import tempfile
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path

import numpy as np

from . import config

PROFILE_VERSION = "temporal-v2-5fps-gray"
SAMPLE_FPS = 5
WIDTH, HEIGHT = 96, 54
MIN_EVENT_FRAMES = 36
MAX_EVENT_FRAMES = 180


@dataclass(frozen=True)
class TemporalProfile:
    frame_count: int
    boundaries: tuple[int, ...]
    change_scores: tuple[float, ...]

    @property
    def events(self):
        return list(zip(self.boundaries[:-1], self.boundaries[1:]))

    def event_for(self, start: int, end: int):
        """Assign an overlapping search hit to one event, never union it."""
        midpoint = (start + end) / 2
        for index, (left, right) in enumerate(self.events):
            if left <= midpoint < right or (index == len(self.events) - 1 and midpoint <= right):
                return index
        return None

    def refine(self, event_index: int, focus=None):
        """Snap only near the event edges, without another cloud request."""
        events = self.events
        event_start, event_end = events[event_index]
        start, end = focus or (event_start, event_end)
        if event_index or start > event_start:
            start = _snap(self.change_scores, start, event_start - 1, end)
        if event_index + 1 < len(events) or end < event_end:
            end = _snap(self.change_scores, end, start, event_end + 1)
        return max(0, start), min(self.frame_count, max(start + 1, end))

    def index_ranges(self):
        """Coarse events plus at most three adaptive detail ranges per long event."""
        ranges = set(self.events)
        for start, end in self.events:
            if end - start < 3 * config.FPS:
                continue
            candidates = []
            lo = math.ceil((start + 24) / 6)
            hi = math.floor((end - 24) / 6)
            for sample in range(lo, min(hi + 1, len(self.change_scores) - 2)):
                score = self.change_scores[sample]
                if score >= max(self.change_scores[sample - 2:sample + 3]):
                    candidates.append((score, sample * 6))
            selected = []
            for _, point in sorted(candidates, reverse=True):
                if all(abs(point - prior) >= 30 for prior in selected):
                    selected.append(point)
                if len(selected) == 2:
                    break
            cuts = [start] + sorted(selected) + [end]
            for left, right in pairwise(cuts):
                if right - left >= 18 and (left, right) != (start, end):
                    ranges.add((left, right))
        return sorted(ranges)


def _snap(scores, boundary, left, right):
    radius = 9  # 0.3 seconds
    lo = max(left + 1, boundary - radius)
    hi = min(right - 1, boundary + radius)
    if lo > hi:
        return boundary
    return max(
        range(lo, hi + 1),
        key=lambda frame: (scores[min(len(scores) - 1, frame // 6)], -abs(frame - boundary)),
    )


def _decode_gray(proxy: Path, cancelled=lambda: False):
    process = subprocess.Popen(
        [
            "ffmpeg", "-nostdin", "-v", "error", "-i", str(proxy),
            "-vf", f"fps={SAMPLE_FPS},scale={WIDTH}:{HEIGHT},format=gray",
            "-f", "rawvideo", "-pix_fmt", "gray", "pipe:1",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    frames = []
    try:
        while True:
            block = process.stdout.read(WIDTH * HEIGHT)
            if not block:
                break
            if len(block) != WIDTH * HEIGHT:
                raise ValueError("Incomplete temporal-analysis frame")
            frames.append(np.frombuffer(block, dtype=np.uint8).copy())
            if cancelled():
                from .media import Cancelled

                raise Cancelled()
        error = process.stderr.read().decode(errors="replace")
        if process.wait() != 0:
            raise ValueError("Could not inspect video motion: " + error[-500:])
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        process.stdout.close()
        process.stderr.close()
    if not frames:
        raise ValueError("No video frames available for temporal analysis")
    return np.stack(frames).reshape(-1, HEIGHT, WIDTH).astype(np.float32) / 255


def _change_scores(frames):
    """Combine shot changes, short-term appearance novelty, motion valleys."""
    count = len(frames)
    if count == 1:
        return np.zeros(1, dtype=np.float32)
    motion = np.r_[0, np.mean(np.abs(frames[1:] - frames[:-1]), axis=(1, 2))]
    score = np.zeros(count, dtype=np.float32)
    for i in range(2, count - 2):
        before = frames[i - 2:i].mean(axis=0)
        after = frames[i:i + 2].mean(axis=0)
        novelty = np.mean(np.abs(before - after))
        valley = max(0.0, (motion[i - 2:i].mean() + motion[i + 1:i + 3].mean()) / 2 - motion[i])
        score[i] = novelty + 0.5 * valley
    pixel_fraction = np.r_[0, np.mean(np.abs(frames[1:] - frames[:-1]) > 0.18, axis=(1, 2))]
    score += np.where(pixel_fraction > 0.38, pixel_fraction * 0.2, 0)
    return score


def _boundaries(scores, motion, frame_count):
    if frame_count <= MIN_EVENT_FRAMES:
        return (0, frame_count)
    samples = len(scores)
    median = float(np.median(scores))
    spread = float(np.median(np.abs(scores - median)))
    threshold = median + max(0.005, 0.8 * spread)
    peaks = [i for i in range(3, samples - 3)
             if scores[i] >= threshold and scores[i] >= max(scores[i - 2:i + 3])]
    typical_motion = float(np.median(motion))
    candidates = []
    for peak in peaks:
        # A gradual action change often peaks after its onset. Find the first
        # low-motion hinge preceding that change, if one exists. An abrupt edit
        # has no such hinge and remains at the peak itself.
        onset = peak
        if scores[peak] < 0.15:  # not a large whole-frame shot cut
            for sample in range(max(2, peak - 10), peak - 1):
                before = motion[max(0, sample - 4):sample]
                if (motion[sample] < typical_motion * 0.78
                        and len(before) and float(np.mean(before)) > motion[sample] * 1.25):
                    onset = sample
                    break
        candidates.append((round(onset * config.FPS / SAMPLE_FPS), float(scores[peak])))
    boundaries = [0]
    while frame_count - boundaries[-1] > MAX_EVENT_FRAMES:
        start = boundaries[-1]
        preferred = min(frame_count, start + 4 * config.FPS)
        options = [(point, strength) for point, strength in candidates
                   if start + MIN_EVENT_FRAMES <= point <= start + MAX_EVENT_FRAMES
                   and frame_count - point >= MIN_EVENT_FRAMES]
        if options:
            chosen = max(options, key=lambda item: (
                item[1]
                - 0.007 * abs(item[0] - preferred) / config.FPS,
                -abs(item[0] - preferred),
            ))[0]
        else:
            # Continuous/static take: bound request length without claiming an
            # action boundary. The UI still describes candidate times as approximate.
            chosen = preferred
        boundaries.append(chosen)
    if frame_count - boundaries[-1] < MIN_EVENT_FRAMES and len(boundaries) > 1:
        boundaries.pop()
    boundaries.append(frame_count)
    return tuple(boundaries)


def analyze_frames(frames, frame_count):
    scores = _change_scores(frames)
    motion = np.r_[0, np.mean(np.abs(frames[1:] - frames[:-1]), axis=(1, 2))]
    return TemporalProfile(frame_count, _boundaries(scores, motion, frame_count), tuple(float(x) for x in scores))


def temporal_profile(proxy: Path, frame_count: int, proxy_hash: str, cancelled=lambda: False):
    """A generated cache, not source data; safe to recompute after interruption."""
    cache = proxy.with_name("temporal-profile.json")
    if cache.is_file():
        try:
            data = json.loads(cache.read_text())
            if (data["version"], data["proxy_hash"], data["frame_count"]) == (
                PROFILE_VERSION, proxy_hash, frame_count
            ):
                return TemporalProfile(frame_count, tuple(data["boundaries"]), tuple(data["scores"]))
        except (OSError, ValueError, KeyError, TypeError):
            pass
    profile = analyze_frames(_decode_gray(proxy, cancelled), frame_count)
    data = {"version": PROFILE_VERSION, "proxy_hash": proxy_hash,
            "frame_count": frame_count, "boundaries": profile.boundaries,
            "scores": profile.change_scores}
    with tempfile.NamedTemporaryFile("w", dir=cache.parent, prefix="temporal-",
                                     suffix=".partial", delete=False) as output:
        temp = Path(output.name)
        json.dump(data, output, separators=(",", ":"))
    try:
        os.replace(temp, cache)
    finally:
        temp.unlink(missing_ok=True)
    return profile


def segment_windows(frame_count):
    """Legacy v2 ranges; new indexing uses a temporal profile instead."""
    windows = []
    start = 0
    while start < frame_count:
        end = min(start + config.VISUAL_WINDOW_FRAMES, frame_count)
        windows.append((start, end))
        if end >= frame_count:
            break
        start += config.VISUAL_STRIDE_FRAMES
    return windows


def sampled_frames(start_frame, end_frame):
    return max(1, math.ceil((end_frame - start_frame) / config.FPS))
