import contextlib
import json
import sqlite3
import time
import uuid
from . import config


def uid():
    return uuid.uuid4().hex


@contextlib.contextmanager
def connect():
    config.DATA.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DATA / "storyroom.sqlite", timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def init():
    from .migrations import migrate
    config.DATA.mkdir(parents=True, exist_ok=True)
    migrate(config.DATA / "storyroom.sqlite")


def rows(sql, params=()):
    with connect() as c:
        return [dict(r) for r in c.execute(sql, params).fetchall()]


def one(sql, params=()):
    result = rows(sql, params)
    return result[0] if result else None


def execute(sql, params=()):
    with connect() as c:
        c.execute(sql, params)


def enqueue(project_id, kind, payload):
    with connect() as c:
        c.execute("BEGIN IMMEDIATE")
        return enqueue_in_transaction(c, project_id, kind, payload)


def enqueue_in_transaction(c, project_id, kind, payload):
    """Queue work in the caller's transaction, without committing it here.

    Import uses this to commit the asset and its processing job together.
    Ordinary callers should use enqueue(), which opens its own transaction.
    """
    if not c.in_transaction:
        raise ValueError("Queuing work requires an active transaction")
    # Suppress duplicate pending work, including repeated button clicks.
    encoded = json.dumps(payload, sort_keys=True)
    old = c.execute(
        "SELECT id FROM jobs WHERE project_id=? AND kind=? AND payload=? AND status IN ('queued','running')",
        (project_id, kind, encoded),
    ).fetchone()
    if old:
        return old[0]
    ident = uid()
    c.execute(
        "INSERT INTO jobs(id,project_id,kind,payload,status,created) VALUES(?,?,?,?,?,?)",
        (ident, project_id, kind, encoded, "queued", time.time()),
    )
    return ident


def cache_get(key):
    r = one("SELECT value FROM cache WHERE key=?", (key,))
    return json.loads(r["value"]) if r else None


def cache_set(key, value):
    execute("INSERT OR REPLACE INTO cache VALUES(?,?)", (key, json.dumps(value)))


def spend():
    return one("SELECT COALESCE(SUM(COALESCE(actual,reserved)),0) AS total FROM usage")[
        "total"
    ]


def reserve(job_id, model, amount):
    with connect() as c:
        c.execute("BEGIN IMMEDIATE")
        total = c.execute(
            "SELECT COALESCE(SUM(COALESCE(actual,reserved)),0) FROM usage"
        ).fetchone()[0]
        if total + amount > config.SPEND_LIMIT:
            raise ValueError(
                "AI budget limit reached. Manual editing remains available."
            )
        ident = uid()
        c.execute(
            "INSERT INTO usage VALUES(?,?,?,?,?,?,?)",
            (ident, job_id, model, amount, None, "reserved", time.time()),
        )
        return ident
