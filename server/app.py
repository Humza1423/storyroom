import hashlib
import json
import os
import shutil
import tempfile
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, HTTPException, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import Field
from . import config, db, media, ai
from .models import (
    Strict,
    ProjectInput,
    BoardInput,
    AnalysisInput,
    SearchInput,
    MomentInput,
    FeedbackInput,
)
from .search import search, features


@asynccontextmanager
async def lifespan(app):
    db.init()
    yield


app = FastAPI(title="Storyroom", lifespan=lifespan)
ORIGINS = {
    f"http://{host}:{port}"
    for host in ("127.0.0.1", "localhost")
    for port in (int(os.getenv("STORYROOM_UI_PORT", "5173")),
                 int(os.getenv("STORYROOM_API_PORT", "8765")))
}
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(ORIGINS),
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "X-Storyroom"],
)


@app.middleware("http")
async def local_only(request: Request, call_next):
    host = request.headers.get("host", "").split(":")[0]
    if host not in ("localhost", "127.0.0.1", "testserver"):
        return JSONResponse({"detail": "Local access only"}, status_code=403)
    origin = request.headers.get("origin")
    if origin and origin not in ORIGINS:
        return JSONResponse({"detail": "Origin not allowed"}, status_code=403)
    if (
        request.method not in ("GET", "HEAD", "OPTIONS")
        and request.headers.get("x-storyroom") != "local"
    ):
        return JSONResponse({"detail": "Missing local request header"}, status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.exception_handler(ValueError)
async def bad_value(request, exc):
    return JSONResponse({"detail": str(exc)}, status_code=400)


def project(pid):
    p = db.one("SELECT * FROM projects WHERE id=?", (pid,))
    if not p:
        raise HTTPException(404, "Project not found")
    return p


def asset(aid):
    a = db.one("SELECT * FROM assets WHERE id=?", (aid,))
    if not a:
        raise HTTPException(404, "Clip not found")
    return a


def validate_board(pid, board):
    assets = {
        a["id"]: a for a in db.rows("SELECT * FROM assets WHERE project_id=?", (pid,))
    }
    ids = set()
    total = 0
    for section in board:
        if section["id"] in ids:
            raise ValueError("Section and selection IDs must be unique")
        ids.add(section["id"])
        for s in section["selections"]:
            a = assets.get(s["asset_id"])
            if not a or a["status"] != "ready":
                raise ValueError(
                    "Selections must reference ready footage in this project"
                )
            if not 0 <= s["start_frame"] < s["end_frame"] <= a["frames"]:
                raise ValueError(
                    "Clip boundaries must be within the source and at least one frame apart"
                )
            if s["id"] in ids:
                raise ValueError("Selection IDs must be unique")
            ids.add(s["id"])
            if s.get("moment_id") and not db.one(
                "SELECT id FROM moments WHERE id=? AND asset_id=?",
                (s["moment_id"], a["id"]),
            ):
                raise ValueError("Moment does not belong to the selected clip")
            total += s["end_frame"] - s["start_frame"]
    if total > 900 * 30:
        raise ValueError("Keep the assembly under 15 minutes")


@app.get("/api/status")
def status():
    return {
        "ai_ready": config.ai_ready(),
        "key_present": bool(os.getenv("GEMINI_API_KEY")),
        "pricing_confirmed": config.PRICING_CONFIRMED,
        "model": config.MODEL,
        "spend": db.spend(),
        "limit": config.SPEND_LIMIT,
        "ffmpeg": bool(shutil.which("ffmpeg")),
        "fps": 30,
        "rates": {
            "input": config.INPUT_RATE,
            "output": config.OUTPUT_RATE,
            "embedding": config.EMBED_RATE,
        },
    }


@app.get("/api/projects")
def projects():
    return db.rows("SELECT id,name,brief,created FROM projects ORDER BY created DESC")


@app.post("/api/projects")
def create_project(data: ProjectInput):
    ident = db.uid()
    db.execute(
        "INSERT INTO projects(id,name,brief,created) VALUES(?,?,?,?)",
        (ident, data.name.strip(), data.brief, time.time()),
    )
    return {"id": ident}


@app.get("/api/projects/{pid}")
def details(pid: str):
    p = project(pid)
    p["board"] = json.loads(p["board"])
    p["assets"] = db.rows(
        "SELECT * FROM assets WHERE project_id=? ORDER BY rowid", (pid,)
    )
    for a in p["assets"]:
        a["provenance"] = json.loads(a["provenance"])
    p["moments"] = db.rows(
        "SELECT m.id,m.asset_id,m.start_frame,m.end_frame,m.description,m.source,m.uncertainty FROM moments m JOIN assets a ON a.id=m.asset_id WHERE a.project_id=?",
        (pid,),
    )
    p["jobs"] = db.rows(
        "SELECT * FROM jobs WHERE project_id=? ORDER BY created DESC LIMIT 40", (pid,)
    )
    for j in p["jobs"]:
        j["result"] = json.loads(j["result"]) if j["result"] else None
        j.pop("payload")
    return p


@app.put("/api/projects/{pid}")
def update_project(pid: str, data: ProjectInput):
    project(pid)
    db.execute(
        "UPDATE projects SET name=?,brief=? WHERE id=?", (data.name, data.brief, pid)
    )
    return {"ok": True}


@app.post("/api/projects/{pid}/import")
def import_file(pid: str, file: UploadFile = File(...)):
    project(pid)
    if Path(file.filename or "").suffix.lower() != ".mp4":
        raise ValueError("Import an H.264 MP4 file")
    if shutil.disk_usage(config.DATA).free < 3_000_000_000:
        raise ValueError("At least 3 GB of free disk space is required")
    folder = config.DATA / "incoming"
    folder.mkdir(exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=folder, suffix=".mp4", delete=False) as temp:
        path = Path(temp.name)
        size = 0
        digest = hashlib.sha256()
        stored = None
        committed = False
        try:
            while chunk := file.file.read(1024 * 1024):
                size += len(chunk)
                if size > config.MAX_BYTES:
                    raise ValueError("Project input limit is 2 GB")
                digest.update(chunk)
                temp.write(chunk)
            temp.flush()
            info = media.probe(path)
            media.validate(info)
            ident = db.uid()
            with db.connect() as c:
                c.execute("BEGIN IMMEDIATE")
                duplicate = c.execute(
                    "SELECT id FROM assets WHERE project_id=? AND hash=?",
                    (pid, digest.hexdigest()),
                ).fetchone()
                if duplicate:
                    return {"id": duplicate[0], "duplicate": True}
                totals = c.execute(
                    "SELECT COUNT(*),COALESCE(SUM(bytes),0),COALESCE(SUM(duration),0) FROM assets WHERE project_id=?",
                    (pid,),
                ).fetchone()
                if (
                    totals[0] >= config.MAX_FILES
                    or totals[1] + size > config.MAX_BYTES
                    or totals[2] + info["duration"] > config.MAX_SECONDS
                ):
                    raise ValueError(
                        "Project limit: 30 clips, 15 minutes, and 2 GB total input"
                    )
                if shutil.disk_usage(config.DATA).free < size * 3 + 1_000_000_000:
                    raise ValueError(
                        "Insufficient disk space for editing copies and proxies"
                    )
                dest = config.asset_dir(ident)
                dest.mkdir(parents=True)
                stored = dest
                shutil.copyfile(path, dest / "original.mp4")
                c.execute(
                    "INSERT INTO assets(id,project_id,name,hash,bytes,duration,frames,width,height,has_audio,status) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        ident,
                        pid,
                        Path(file.filename).name,
                        digest.hexdigest(),
                        size,
                        info["duration"],
                        info["frames"],
                        info["width"],
                        info["height"],
                        int(info["has_audio"]),
                        "processing",
                    ),
                )
                # A registered asset must always have its preparation job.
                job = db.enqueue_in_transaction(
                    c, pid, "normalize", {"asset_id": ident}
                )
            committed = True
            return {"id": ident, "job_id": job, "duplicate": False}
        finally:
            path.unlink(missing_ok=True)
            if stored is not None and not committed:
                # Only remove this request's new managed copy, never the user's source.
                # Abrupt process termination can still leave an orphan directory.
                (stored / "original.mp4").unlink(missing_ok=True)
                stored.rmdir()


@app.get("/api/assets/{aid}/{kind}")
def media_file(aid: str, kind: Literal["proxy", "thumbnail", "edit"]):
    asset(aid)
    filename, mime = {
        "proxy": ("proxy.mp4", "video/mp4"),
        "edit": ("edit.mp4", "video/mp4"),
        "thumbnail": ("thumb.jpg", "image/jpeg"),
    }[kind]
    path = config.asset_dir(aid) / filename
    if not path.exists():
        raise HTTPException(
            404, "Media not available. Wait for preparation or retry its job."
        )
    return FileResponse(path, media_type=mime)


class Provenance(Strict):
    source: str = Field(default="", max_length=2000)
    author: str = Field(default="", max_length=200)
    license: str = Field(default="", max_length=1000)
    cloud_analysis: bool = False
    training: bool = False
    redistribution: bool = False


@app.put("/api/assets/{aid}/provenance")
def provenance(aid: str, data: Provenance):
    asset(aid)
    if (data.cloud_analysis or data.training) and not data.license.strip():
        raise ValueError(
            "Record the permission or license before enabling analysis or training"
        )
    db.execute(
        "UPDATE assets SET provenance=? WHERE id=?", (data.model_dump_json(), aid)
    )
    return {"ok": True}


@app.post("/api/assets/{aid}/moments")
def add_moment(aid: str, data: MomentInput):
    a = asset(aid)
    if a["status"] != "ready" or not data.start_frame < data.end_frame <= a["frames"]:
        raise ValueError("Moment must reference a valid range in prepared footage")
    ident = db.uid()
    db.execute(
        "INSERT INTO moments VALUES(?,?,?,?,?,?,?,?,?)",
        (
            ident,
            aid,
            data.start_frame,
            data.end_frame,
            data.description,
            "manual",
            "",
            None,
            None,
        ),
    )
    return {"id": ident}


@app.put("/api/projects/{pid}/board")
def save_board(pid: str, data: BoardInput):
    board = [s.model_dump() for s in data.sections]
    validate_board(pid, board)
    with db.connect() as c:
        c.execute("BEGIN IMMEDIATE")
        p = c.execute(
            "SELECT board,revision FROM projects WHERE id=?", (pid,)
        ).fetchone()
        if not p:
            raise HTTPException(404, "Project not found")
        if p["revision"] != data.revision:
            raise HTTPException(
                409, "Board changed in another tab. Reload before editing."
            )
        c.execute(
            "INSERT INTO revisions VALUES(?,?,?)", (pid, p["revision"], p["board"])
        )
        c.execute(
            "UPDATE projects SET board=?,revision=revision+1 WHERE id=?",
            (json.dumps(board), pid),
        )
    return {"revision": data.revision + 1}


@app.post("/api/projects/{pid}/undo")
def undo(pid: str, data: dict):
    with db.connect() as c:
        c.execute("BEGIN IMMEDIATE")
        p = c.execute("SELECT revision FROM projects WHERE id=?", (pid,)).fetchone()
        if not p:
            raise HTTPException(404, "Project not found")
        if data.get("revision") != p["revision"]:
            raise HTTPException(409, "Board changed. Reload first.")
        previous = c.execute(
            "SELECT * FROM revisions WHERE project_id=? ORDER BY revision DESC LIMIT 1",
            (pid,),
        ).fetchone()
        if not previous:
            raise ValueError("No earlier revision to restore")
        c.execute(
            "UPDATE projects SET board=?,revision=revision+1 WHERE id=?",
            (previous["board"], pid),
        )
        c.execute(
            "DELETE FROM revisions WHERE project_id=? AND revision=?",
            (pid, previous["revision"]),
        )
    return {"ok": True}


@app.post("/api/projects/{pid}/search")
def find_moments(pid: str, data: SearchInput):
    project(pid)
    return search(pid, data.query, data.semantic)


@app.post("/api/projects/{pid}/analysis-estimate")
def estimate_analysis(pid: str, data: AnalysisInput):
    project(pid)
    total = 0
    for aid in set(data.asset_ids):
        a = asset(aid)
        if a["project_id"] != pid:
            raise ValueError("Clip is not in this project")
        for start in range(0, max(1, int(a["duration"])), 28):
            total += ai.estimate(min(30, a["duration"] - start), 1000) + 0.01
    return {
        "estimated_usd": round(total, 4),
        "recorded_usd": db.spend(),
        "limit": config.SPEND_LIMIT,
        "note": "Conservative estimate before cache savings; provider billing is authoritative.",
    }


@app.post("/api/projects/{pid}/analyze")
def start_analysis(pid: str, data: AnalysisInput):
    project(pid)
    if not config.ai_ready():
        raise ValueError("Configure a Gemini key and confirm prices in .env first")
    selected = [asset(aid) for aid in set(data.asset_ids)]
    for a in selected:
        if a["project_id"] != pid or a["status"] != "ready":
            raise ValueError("Choose prepared clips in this project")
        if not json.loads(a["provenance"]).get("cloud_analysis"):
            raise ValueError(f"Record cloud-analysis permission for {a['name']} first")
    return {
        "job_ids": [db.enqueue(pid, "analyze", {"asset_id": a["id"]}) for a in selected]
    }


@app.post("/api/projects/{pid}/jobs/{kind}")
def start_job(
    pid: str, kind: Literal["story", "rerank", "render", "export"], data: SearchInput
):
    p = project(pid)
    if kind in ("story", "rerank"):
        if not config.ai_ready():
            raise ValueError("Configure Gemini before requesting suggestions")
        if not p["brief"].strip():
            raise ValueError("Write and save your creative brief first")
        payload = {"query": data.query, "brief_revision": p["brief"]}
    else:
        board = json.loads(p["board"])
        validate_board(pid, board)
        if not any(s["selections"] for s in board):
            raise ValueError("Add a clip to your story first")
        payload = {"name": p["name"], "board": board, "revision": p["revision"]}
    return {"job_id": db.enqueue(pid, kind, payload)}


@app.post("/api/jobs/{jid}/{action}")
def manage_job(jid: str, action: Literal["cancel", "retry"]):
    j = db.one("SELECT * FROM jobs WHERE id=?", (jid,))
    if not j:
        raise HTTPException(404, "Job not found")
    if action == "cancel":
        db.execute(
            "UPDATE jobs SET cancel=1,status=CASE WHEN status='queued' THEN 'cancelled' ELSE status END WHERE id=? AND status IN ('queued','running')",
            (jid,),
        )
        return {"ok": True}
    if j["status"] not in ("failed", "cancelled"):
        raise ValueError("Only failed or cancelled work can be retried")
    return {"job_id": db.enqueue(j["project_id"], j["kind"], json.loads(j["payload"]))}


@app.get("/api/jobs/{jid}/download")
def download(jid: str, format: Literal["default", "otio", "json"] = "default"):
    j = db.one("SELECT * FROM jobs WHERE id=?", (jid,))
    if not j or j["status"] != "done" or j["kind"] not in ("export", "render"):
        raise HTTPException(404, "Completed export not found")
    suffix = (
        ".mp4"
        if j["kind"] == "render"
        else {"default": ".xml", "otio": ".otio", "json": ".json"}[format]
    )
    path = config.DATA / "exports" / f"{jid}{suffix}"
    if not path.exists():
        raise HTTPException(404, "Export file missing; run export again")
    return FileResponse(path, filename=f"storyroom-{jid[:8]}{suffix}")


@app.post("/api/projects/{pid}/feedback")
def feedback(pid: str, data: FeedbackInput):
    p = project(pid)
    m = db.one(
        "SELECT m.*,a.provenance FROM moments m JOIN assets a ON a.id=m.asset_id WHERE m.id=? AND a.project_id=?",
        (data.moment_id, pid),
    )
    if not m:
        raise HTTPException(404, "Moment not found")
    if not json.loads(m["provenance"]).get("training"):
        raise ValueError("Record training permission for this footage first")
    # Compute features server-side, never trust browser-supplied scores.
    query = data.query or data.section
    # Labeling itself never starts a paid request.
    hits = search(pid, query, semantic=False)
    match = next((h for h in hits if h["id"] == m["id"]), None)
    f = match["features"] if match else features(query, m)
    cached = ai.cached_embedding(query)
    if cached and m["embedding"] and m["embedding_model"] == config.EMBED_MODEL:
        stored = json.loads(m["embedding"])
        if len(cached) == len(stored):
            f[1] = sum(x * y for x, y in zip(cached, stored))
    db.execute(
        "INSERT INTO feedback VALUES(?,?,?,?,?,?,?,?,?,?)",
        (
            db.uid(),
            pid,
            data.moment_id,
            p["brief"],
            data.section,
            data.rating,
            data.reason,
            json.dumps(f),
            data.footage_group,
            time.time(),
        ),
    )
    return {"ok": True}


@app.get("/api/feedback")
def labels():
    result = db.rows("SELECT * FROM feedback ORDER BY created")
    for r in result:
        r["features"] = json.loads(r["features"])
    return result


if (config.ROOT / "dist").exists():
    app.mount(
        "/", StaticFiles(directory=config.ROOT / "dist", html=True), name="frontend"
    )
