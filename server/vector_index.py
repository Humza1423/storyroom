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
