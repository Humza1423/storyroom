"""Small exact-cosine search over the visual vectors stored in SQLite."""

from __future__ import annotations

import hashlib


class ExactVectorIndex:
    """The v1 adapter; intentionally avoids a runtime ANN dependency."""

    def search(self, query_vector, rows, limit=20):
        scored = []
        for row in rows:
            vector = row["embedding"]
            if len(vector) != len(query_vector):
                continue
            score = sum(left * right for left, right in zip(query_vector, vector))
            scored.append((score, row))
        scored.sort(
            key=lambda item: (
                -item[0],
                item[1]["asset_id"],
                item[1]["start_frame"],
                item[1]["end_frame"],
            )
        )
        return scored[:limit]


def collapse_overlapping(scored, limit=5):
    """Keep the strongest playable window; suppress overlapping duplicates.

    Do not union adjacent ranges: doing so can stretch a result across distinct
    actions and imply temporal precision the video embedding does not provide.
    """
    candidates = []
    for score, row in scored:
        duplicate = any(
            item["asset_id"] == row["asset_id"]
            and max(item["start_frame"], row["start_frame"])
            < min(item["end_frame"], row["end_frame"])
            for item in candidates
        )
        if not duplicate:
            candidates.append(
                {
                    "asset_id": row["asset_id"],
                    "asset_name": row["asset_name"],
                    "start_frame": row["start_frame"],
                    "end_frame": row["end_frame"],
                    "score": score,
                }
            )
    for rank, candidate in enumerate(candidates[:limit], start=1):
        digest = hashlib.sha256(
            (
                f"{candidate['asset_id']}:{candidate['start_frame']}"
                f":{candidate['end_frame']}"
            ).encode()
        ).hexdigest()[:24]
        candidate.update(id=f"visual-{digest}", rank=rank, kind="visual")
        candidate.pop("score", None)
    return candidates[:limit]


def rank_distinct_events(scored, profiles, limit=5):
    """Aggregate semantic evidence by local event identity, not overlap.

    A neighboring action can overlap a retrieval window; its midpoint assigns
    that window to only one proposed event. Repeated nonadjacent occurrences
    have different event IDs even when they depict the same action.
    """
    grouped = {}
    for score, row in scored:
        profile = profiles.get(row["asset_id"])
        if profile is None:
            continue
        event = profile.event_for(row["start_frame"], row["end_frame"])
        if event is None:
            continue
        key = (row["asset_id"], event)
        group = grouped.setdefault(key, {"scores": [], "row": row, "profile": profile})
        # A crossing window can contain the next action; discount it instead
        # of stretching the result across both events.
        event_start, event_end = profile.events[event]
        overlap = max(0, min(row["end_frame"], event_end) - max(row["start_frame"], event_start))
        coverage = overlap / max(1, row["end_frame"] - row["start_frame"])
        group["scores"].append((score * (0.85 + 0.15 * coverage), row))
    ranked = []
    for (asset_id, event), group in grouped.items():
        best = sorted((score for score, _ in group["scores"]), reverse=True)[:2]
        # Preserve the strongest semantic observation. The old mean-of-three
        # rule buried a real brief action under weaker neighboring subranges.
        strength = 0.7 * best[0] + 0.3 * (sum(best) / len(best))
        strength += 0.004 * min(2, len(best) - 1)
        start, end = group["profile"].refine(event)
        details = [(score, row) for score, row in group["scores"]
                   if (row["start_frame"], row["end_frame"]) != group["profile"].events[event]]
        if len(details) >= 2:
            strongest = max(score for score, _ in details)
            supporting = sorted(
                (row["start_frame"], row["end_frame"], score)
                for score, row in details if score >= strongest - 0.02
            )
            clusters = []
            for left, right, score in supporting:
                if clusters and left <= clusters[-1][1] + 6:
                    prior = clusters[-1]
                    clusters[-1] = (prior[0], max(prior[1], right), prior[2] + score, prior[3] + 1)
                else:
                    clusters.append((left, right, score, 1))
            if clusters:
                focus = max(clusters, key=lambda c: (c[2] / c[3] + 0.01 * min(c[3], 3), c[3]))
                start, end = group["profile"].refine(
                    event, (max(start, focus[0]), min(end, focus[1]))
                )
        row = group["row"]
        ranked.append((strength, asset_id, event, start, end, row["asset_name"]))
    ranked.sort(key=lambda item: (-item[0], item[1], item[3]))
    candidates = []
    for rank, (_, asset_id, event, start, end, name) in enumerate(ranked[:limit], 1):
        digest = hashlib.sha256(f"{asset_id}:{event}:{start}:{end}".encode()).hexdigest()[:24]
        candidates.append({
            "id": f"visual-{digest}", "rank": rank, "kind": "visual",
            "asset_id": asset_id, "asset_name": name,
            "start_frame": start, "end_frame": end,
        })
    return candidates
