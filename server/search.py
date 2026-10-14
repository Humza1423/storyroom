import json
import re
from . import db, ai, config
from .vector_index import ExactVectorIndex, collapse_overlapping


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


def search_visual(project_id, query, limit=5):
    if not query.strip():
        return []
    provider = ai.embedding_provider()
    rows = db.rows(
        """SELECT v.id,v.asset_id,a.name AS asset_name,a.provenance,
                  v.start_frame,v.end_frame,v.embedding
           FROM visual_segments v JOIN assets a ON a.id=v.asset_id
           WHERE a.project_id=? AND a.status='ready'
             AND a.visual_proxy_hash=v.proxy_hash
             AND v.provider=? AND v.model=? AND v.dimensions=?
             AND v.index_version=?""",
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
        raise ValueError("Index prepared clips for visual search first.")
    query_vector = ai.embedding_provider().embed_text_query(query)
    for row in rows:
        row.pop("provenance", None)
        row["embedding"] = json.loads(row["embedding"])
    scored = ExactVectorIndex().search(query_vector, rows, limit=40)
    candidates = collapse_overlapping(scored, limit=limit)
    for candidate in candidates:
        candidate["media_url"] = f"/api/assets/{candidate['asset_id']}/proxy"
    return candidates
