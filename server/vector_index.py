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


def collapse_overlapping(scored, limit=5, max_group_frames=12 * 30):
    """Merge only overlapping top-ranked windows; cap broad chained ranges."""
    groups = []
    for score, row in scored:
        matching = [
            group
            for group in groups
            if group["asset_id"] == row["asset_id"]
            and max(group["start_frame"], row["start_frame"])
            < min(group["end_frame"], row["end_frame"])
            and max(group["end_frame"], row["end_frame"])
            - min(group["start_frame"], row["start_frame"])
            <= max_group_frames
        ]
        if matching:
            group = matching[0]
            start = min(
                row["start_frame"], *(item["start_frame"] for item in matching)
            )
            end = max(row["end_frame"], *(item["end_frame"] for item in matching))
            if end - start <= max_group_frames:
                group["start_frame"] = start
                group["end_frame"] = end
                group["score"] = max(score, *(item["score"] for item in matching))
                group["segments"] += 1 + sum(
                    item["segments"] for item in matching[1:]
                )
                for other in matching[1:]:
                    groups.remove(other)
                continue
        groups.append(
            {
                "asset_id": row["asset_id"],
                "asset_name": row["asset_name"],
                "start_frame": row["start_frame"],
                "end_frame": row["end_frame"],
                "score": score,
                "segments": 1,
            }
        )
    groups.sort(
        key=lambda row: (
            -row["score"],
            row["asset_id"],
            row["start_frame"],
            row["end_frame"],
        )
    )
    for rank, group in enumerate(groups[:limit], start=1):
        digest = hashlib.sha256(
            f"{group['asset_id']}:{group['start_frame']}:{group['end_frame']}".encode()
        ).hexdigest()[:24]
        group.update(id=f"visual-{digest}", rank=rank, kind="visual")
        group.pop("score", None)
        group.pop("segments", None)
    return groups[:limit]
