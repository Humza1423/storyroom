import json
import re

from . import ai, config, db
from .media import sha256_file
from .vector_index import ExactVectorIndex, rank_distinct_events
from .visual_index import segment_windows, temporal_profile

# Verification is a paid/rate-limited video request, not a local vector lookup.
# Search a bounded shortlist; a creator can refine the query to inspect others.
MAX_VISUAL_VERIFICATIONS = 5


def features(query, moment, semantic=0.0):
    q = set(re.findall(r"\w+", query.lower()))
    d = set(re.findall(r"\w+", moment["description"].lower()))
    lexical = len(q & d) / max(1, len(q))
    duration = (moment["end_frame"] - moment["start_frame"]) / 30
    return [
        lexical,
        semantic,
        min(duration, 30) / 30,
        float(not bool(moment.get("uncertainty"))),
    ]


def search(project_id, query, semantic=False, limit=50):
    moments = db.rows(
        "SELECT m.*,a.name FROM moments m JOIN assets a ON a.id=m.asset_id WHERE a.project_id=? AND a.status='ready'",
        (project_id,),
    )
    vector = ai.embed(query) if semantic and query.strip() else None
    terms = re.findall(r"\w+", query)
    matched = set()
    if terms:
        fts = " OR ".join('"' + t + '"' for t in terms)
        matched = {
            r["id"]
            for r in db.rows(
                "SELECT id FROM moment_fts WHERE moment_fts MATCH ?", (fts,)
            )
        }
    result = []
    for m in moments:
        sim = 0.0
        if vector and m["embedding"] and m["embedding_model"] == config.EMBED_MODEL:
            other = json.loads(m["embedding"])
            if len(other) == len(vector):
                sim = sum(a * b for a, b in zip(vector, other))
        f = features(query, m, sim)
        m["score"] = round(0.35 * f[0] + 0.65 * max(0, sim), 5) if vector else f[0]
        m["features"] = f
        m.pop("embedding", None)
        if not query.strip() or m["id"] in matched or (vector and sim > 0.25):
            result.append(m)
    return sorted(result, key=lambda m: (-m["score"], m["asset_id"], m["start_frame"]))[
        :limit
    ]


def search_visual(project_id, query, limit=5, trace=None, status=None):
    if not query.strip():
        return []
    provider = ai.embedding_provider()
    rows = db.rows(
        """SELECT v.id,v.asset_id,a.name AS asset_name,a.provenance,
                  a.frames,a.visual_proxy_hash,v.index_version,
                  v.start_frame,v.end_frame,v.embedding
           FROM visual_segments v JOIN assets a ON a.id=v.asset_id
           WHERE a.project_id=? AND a.status='ready'
             AND a.visual_proxy_hash=v.proxy_hash
             AND v.provider=? AND v.model=? AND v.dimensions=?
             AND v.index_version IN (?, 'visual-v3-adaptive-temporal-v2',
                                     'visual-v2-2s-1s-1fps')""",
        (
            project_id,
            provider.provider,
            provider.model,
            config.EMBED_DIMENSIONS,
            config.VISUAL_INDEX_VERSION,
        ),
    )
    rows = [row for row in rows if json.loads(row["provenance"]).get("cloud_analysis")]
    if not rows:
        raise ValueError(
            "No visual index is available for this project's permitted clips. "
            "In Footage, check each clip's cloud-analysis permission, then "
            "choose Visual AI → Estimate & index permitted clips and wait for Activity to finish."
        )
    profiles = {}
    for row in rows:
        row.pop("provenance", None)
        if row["asset_id"] not in profiles:
            proxy = config.asset_dir(row["asset_id"]) / "proxy.mp4"
            if not proxy.is_file():
                raise ValueError(f"Playback proxy is missing for {row['asset_name']}; retry media preparation.")
            if sha256_file(proxy) != row["visual_proxy_hash"]:
                raise ValueError(f"Playback proxy changed for {row['asset_name']}; reindex that clip.")
            profiles[row["asset_id"]] = temporal_profile(
                proxy, row["frames"], row["visual_proxy_hash"]
            )
    # Use a previous complete index while a newer version is only partially
    # written. Without this, a single new row could hide a usable full index.
    versions = (config.VISUAL_INDEX_VERSION,
                "visual-v3-adaptive-temporal-v2", "visual-v2-2s-1s-1fps")
    chosen = {}
    for asset_id, profile in profiles.items():
        counts = {version: sum(r["asset_id"] == asset_id and r["index_version"] == version
                               for r in rows) for version in versions}
        expected = (len(profile.index_ranges()), len(profile.events),
                    len(segment_windows(profile.frame_count)))
        chosen[asset_id] = next(
            (version for version, total in zip(versions, expected)
             if counts[version] >= total),
            next(version for version in versions if counts[version]),
        )
    rows = [row for row in rows if row["index_version"] == chosen[row["asset_id"]]]
    query_vector = ai.embedding_provider().embed_text_query(query)
    for row in rows:
        row["embedding"] = json.loads(row["embedding"])
    scored = ExactVectorIndex().search(query_vector, rows, limit=len(rows))
    # Keep raw cosine scores inside the ranking pipeline. The API deliberately
    # does not expose them as confidence values.
    ranked = rank_distinct_events(scored, profiles, limit=len(rows))
    # First check distinct sources, then fill the bounded shortlist with more
    # occurrences. This lets a true match survive a visually similar source
    # that happens to dominate the cosine ranking.
    shortlist = []
    per_asset = {}
    for candidate in ranked:
        asset_id = candidate["asset_id"]
        if per_asset.get(asset_id, 0) < 2:
            shortlist.append(candidate)
            per_asset[asset_id] = per_asset.get(asset_id, 0) + 1
        if len(shortlist) == MAX_VISUAL_VERIFICATIONS:
            break
    if len(shortlist) < MAX_VISUAL_VERIFICATIONS:
        shortlist.extend(candidate for candidate in ranked
                         if candidate not in shortlist)
    shortlist = shortlist[:MAX_VISUAL_VERIFICATIONS]

    accepted = []
    checked = 0
    for candidate in shortlist:
        asset_id = candidate["asset_id"]
        proxy = config.asset_dir(asset_id) / "proxy.mp4"
        proxy_hash = next(row["visual_proxy_hash"] for row in rows
                          if row["asset_id"] == asset_id)
        try:
            verdict = ai.verify_visual_match(
                query, proxy, proxy_hash,
                candidate["start_frame"], candidate["end_frame"],
            )
        except Exception as exc:
            code = getattr(exc, "code", getattr(exc, "status_code", None))
            safe_detail = getattr(exc, "safe_message", None)
            if accepted and status is not None:
                status["warning"] = (
                    "Search stopped before checking every candidate: "
                    + (safe_detail or "video verification is unavailable")
                    + ". Only confirmed matches are shown."
                )
                status["checked_candidates"] = checked
                status["incomplete"] = True
                break
            if safe_detail:
                raise ValueError(
                    f"{safe_detail}. No unverified results were shown; "
                    "retry later or use manual search."
                ) from exc
            if code == 429:
                raise ValueError(
                    "Gemini video verification has no available quota for this API "
                    "project right now. No unverified matches were shown. Check "
                    "your AI Studio model quota or use manual search."
                ) from exc
            raise ValueError(
                "Visual verification is unavailable. No unverified results were shown; "
                "retry later or use manual search."
            ) from exc
        checked += 1
        matched = verdict.decision == "match" and bool(verdict.visible_evidence.strip())
        if trace is not None:
            trace.append({
                "asset_id": asset_id,
                "start_frame": candidate["start_frame"],
                "end_frame": candidate["end_frame"],
                "embedding_score": candidate["score"],
                "verdict": verdict.decision,
                "evidence": verdict.visible_evidence,
                "accepted": matched,
            })
        if matched:
            result = dict(candidate)
            result.pop("score", None)
            result["rank"] = len(accepted) + 1
            result["media_url"] = f"/api/assets/{asset_id}/proxy"
            accepted.append(result)
        if len(accepted) >= limit:
            break
    if status is not None and not status.get("incomplete"):
        status["checked_candidates"] = checked
        status["incomplete"] = len(ranked) > checked and len(accepted) < limit
        if status["incomplete"]:
            status["warning"] = (
                f"Only the first {checked} ranked moments were verified to limit cloud requests. "
                "Try a more specific search if the moment you want is missing."
            )
    return accepted
