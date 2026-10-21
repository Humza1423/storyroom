import json
import re

from . import ai, config, db
from .media import sha256_file
from .vector_index import ExactVectorIndex, rank_distinct_events
from .visual_index import segment_windows, temporal_profile

# Verification is a paid/rate-limited video request, not a local vector lookup.
# Search a bounded shortlist; a creator can refine the query to inspect others.
MAX_VISUAL_VERIFICATIONS = 5
MAX_VISUAL_PAGES = 8


def _take_visual_shortlist(ranked):
    """Preserve the existing five-candidate ordering within one page."""
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
    return shortlist[:MAX_VISUAL_VERIFICATIONS]


def _visual_candidate_page(ranked, page):
    """Page *verification candidates*, never unverified results.

    Preserve page zero's existing source cap, then expose remaining events in
    global relevance order. Reapplying the cap on each page would repeatedly
    postpone a real repeated action in the strongest source.
    """
    if type(page) is not int or not 0 <= page < MAX_VISUAL_PAGES:
        raise ValueError(f"Visual search page must be between 0 and {MAX_VISUAL_PAGES - 1}.")
    first_page = _take_visual_shortlist(ranked)
    first_ids = {candidate["id"] for candidate in first_page}
    remaining = [candidate for candidate in ranked if candidate["id"] not in first_ids]
    if page == 0:
        return first_page, bool(remaining) and MAX_VISUAL_PAGES > 1
    offset = (page - 1) * MAX_VISUAL_VERIFICATIONS
    shortlist = remaining[offset:offset + MAX_VISUAL_VERIFICATIONS]
    if not shortlist:
        raise ValueError("No more visual search candidates are available on that page.")
    has_more = (offset + MAX_VISUAL_VERIFICATIONS < len(remaining)
                and page + 1 < MAX_VISUAL_PAGES)
    return shortlist, has_more


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


def search_visual(project_id, query, limit=5, trace=None, status=None, page=0):
    if type(page) is not int or not 0 <= page < MAX_VISUAL_PAGES:
        raise ValueError(f"Visual search page must be between 0 and {MAX_VISUAL_PAGES - 1}.")
    if not query.strip():
        if status is not None:
            status.update(page=page, has_more=False)
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
    shortlist, has_more = _visual_candidate_page(ranked, page)
    if status is not None:
        status.update(page=page, has_more=has_more)

    hashes = {row["asset_id"]: row["visual_proxy_hash"] for row in rows}
    specs = [
        (
            f"c{index + 1}",
            config.asset_dir(candidate["asset_id"]) / "proxy.mp4",
            hashes[candidate["asset_id"]],
            candidate["start_frame"],
            candidate["end_frame"],
        )
        for index, candidate in enumerate(shortlist)
    ]
    verdicts, error = ai.verify_visual_matches(query, specs)
    accepted = []
    checked = 0
    for spec, candidate in zip(specs, shortlist, strict=True):
        verdict = verdicts.get(spec[0])
        if verdict is None:
            continue
        checked += 1
        asset_id = candidate["asset_id"]
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
    if error:
        safe_detail = getattr(error, "safe_message", None)
        detail = safe_detail or "Video verification is unavailable"
        if not accepted or status is None:
            raise ValueError(
                f"{detail}. No unverified results were shown; retry later or use manual search."
            ) from error
        status["warning"] = (
            f"Search is incomplete: {detail.rstrip('.')}"
            ". Only confirmed matches are shown."
        )
        status["checked_candidates"] = checked
        status["incomplete"] = True
    if status is not None and not status.get("incomplete"):
        status["checked_candidates"] = checked
        status["incomplete"] = (
            (len(ranked) > checked if page == 0 else has_more)
            and len(accepted) < limit
        )
        if status["incomplete"]:
            status["warning"] = (
                f"Only the first {checked} ranked moments were verified to limit cloud requests. "
                "Try a more specific search if the moment you want is missing."
                if page == 0 else
                f"Only {checked} moments on page {page + 1} were verified to limit cloud requests. "
                "Choose the next page or refine your search if the moment is missing."
            )
    if (status is not None and page == MAX_VISUAL_PAGES - 1
            and len(ranked) > MAX_VISUAL_PAGES * MAX_VISUAL_VERIFICATIONS):
        status["incomplete"] = True
        status.setdefault(
            "warning",
            "Search reached its eight-page safety limit. Refine your description "
            "to inspect remaining moments; unverified footage was not shown.",
        )
    return accepted
