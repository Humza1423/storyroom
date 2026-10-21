"""Bounded, query-aware timing proposals on the normalized 30-fps clock.

This is an opt-in experiment. The existing motion-based search cut remains the
default and a model-proposed boundary never bypasses the visual verifier.
"""

from dataclasses import dataclass
from math import floor, isfinite
from pathlib import Path

from . import config

CONTEXT_MARGIN_FRAMES = 75  # At most 2.5 seconds on each side.
MAX_CONTEXT_FRAMES = 240  # At most eight seconds per candidate.
MAX_ACTION_FRAMES = 180  # Do not turn a short match into a whole-file clip.
MAX_ANCHOR_GAP_FRAMES = 60  # Allow a nearby onset missed by the original cut.


@dataclass(frozen=True)
class LocalizationCandidate:
    candidate_id: str
    proxy: Path
    proxy_hash: str
    anchor_start: int
    anchor_end: int
    asset_frames: int
    context_start: int
    context_end: int

    @property
    def context_frames(self):
        return self.context_end - self.context_start


def candidate_context(candidate_id, proxy, proxy_hash, start, end, asset_frames):
    """Expand a verified hit only within the source and an eight-second cap."""
    if not (0 <= start < end <= asset_frames):
        raise ValueError("Invalid verified candidate boundaries")
    if end - start > MAX_CONTEXT_FRAMES:
        raise ValueError("Verified candidate is too long for localization")
    room = MAX_CONTEXT_FRAMES - (end - start)
    before = min(CONTEXT_MARGIN_FRAMES, start, room // 2)
    after = min(CONTEXT_MARGIN_FRAMES, asset_frames - end, room - before)
    return LocalizationCandidate(
        candidate_id, Path(proxy), proxy_hash, start, end, asset_frames,
        start - before, end + after,
    )


def localized_frames(candidate, start_seconds, end_seconds):
    """Reject impossible or unrelated spans before converting seconds to frames."""
    if (isinstance(start_seconds, bool) or isinstance(end_seconds, bool)
            or not isinstance(start_seconds, (int, float))
            or not isinstance(end_seconds, (int, float))):
        raise TypeError("Localization times must be numbers")
    duration = candidate.context_frames / config.FPS
    if not (isfinite(start_seconds) and isfinite(end_seconds)
            and 0 <= start_seconds < end_seconds <= duration + 1e-6):
        raise ValueError("Localization times fall outside the supplied context")
    start = candidate.context_start + floor(start_seconds * config.FPS + 0.5)
    end = candidate.context_start + floor(end_seconds * config.FPS + 0.5)
    if not (candidate.context_start <= start < end <= candidate.context_end):
        raise ValueError("Localization does not map to a playable frame range")
    if end - start > MAX_ACTION_FRAMES:
        raise ValueError("Localized action is too long")
    gap = max(candidate.anchor_start - end, start - candidate.anchor_end, 0)
    if gap > MAX_ANCHOR_GAP_FRAMES:
        raise ValueError("Localized action is too far from the verified hit")
    return start, end


def validate_cached_localization(candidate, value):
    """A damaged or stale cache entry must never bypass frame validation."""
    if not isinstance(value, dict):
        raise TypeError("Invalid cached localization")
    decision = value.get("decision")
    if decision == "match":
        start, end = value.get("start_frame"), value.get("end_frame")
        evidence = value.get("visible_evidence")
        if (type(start) is not int or type(end) is not int
                or not isinstance(evidence, str) or not evidence.strip()):
            raise ValueError("Invalid cached localized match")
        if not (candidate.context_start <= start < end <= candidate.context_end):
            raise ValueError("Cached localization is outside the context")
        if end - start > MAX_ACTION_FRAMES:
            raise ValueError("Cached localized action is too long")
        gap = max(candidate.anchor_start - end, start - candidate.anchor_end, 0)
        if gap > MAX_ANCHOR_GAP_FRAMES:
            raise ValueError("Cached action is too far from the verified hit")
        return {"decision": decision, "visible_evidence": evidence,
                "start_frame": start, "end_frame": end}
    if decision in ("uncertain", "no_match") and not value.get("start_frame") and not value.get("end_frame"):
        return {"decision": decision, "visible_evidence": ""}
    raise ValueError("Invalid cached localization decision")
