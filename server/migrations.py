"""Ordered transactional upgrades; never executescript inside a transaction."""

from pathlib import Path
import sqlite3
import fcntl
import uuid


def initial_schema(conn):
    statement = ""
    for line in Path(__file__).with_name("schema_v1.sql").read_text().splitlines(True):
        statement += line
        if sqlite3.complete_statement(statement):
            conn.execute(statement)
            statement = ""
    if statement.strip():
        raise RuntimeError("Incomplete initial schema statement")


def visual_segments(conn):
    conn.execute("ALTER TABLE assets ADD COLUMN visual_proxy_hash TEXT")
    conn.execute(
        """CREATE TABLE visual_segments(
            id TEXT PRIMARY KEY,
            asset_id TEXT NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
            start_frame INTEGER NOT NULL CHECK(start_frame >= 0),
            end_frame INTEGER NOT NULL CHECK(end_frame > start_frame),
            provider TEXT NOT NULL,
            model TEXT NOT NULL,
            dimensions INTEGER NOT NULL CHECK(dimensions > 0),
            index_version TEXT NOT NULL,
            proxy_hash TEXT NOT NULL,
            sampled_frames INTEGER NOT NULL CHECK(sampled_frames > 0),
            embedding TEXT NOT NULL,
            created REAL NOT NULL,
            UNIQUE(asset_id,start_frame,end_frame,provider,model,dimensions,
                   index_version,proxy_hash)
        )"""
    )
    conn.execute(
        "CREATE INDEX visual_segments_asset_model ON visual_segments"
        "(asset_id,provider,model,dimensions,index_version,proxy_hash)"
    )


MIGRATIONS = (initial_schema, visual_segments)


def migrate(path, migrations=MIGRATIONS):
    # journal_mode itself can race before SQLite acquires its transaction lock.
    with open(str(path) + ".migration.lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        _migrate(path, migrations)


def _migrate(path, migrations):
    """Serialize API/worker startup; backup committed WAL state before upgrading.

    Migration functions issue individual SQL statements, never commit/executescript.
    All pending versions and their history records commit together.
    """
    path = Path(path)
    conn = sqlite3.connect(path, timeout=30)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("BEGIN EXCLUSIVE")
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE name='schema_versions'"
        ).fetchone()
        versions = (
            [
                r[0]
                for r in conn.execute(
                    "SELECT version FROM schema_versions ORDER BY version"
                )
            ]
            if exists
            else []
        )
        if versions and (
            not all(isinstance(v, int) for v in versions)
            or versions != list(range(1, max(versions) + 1))
        ):
            raise RuntimeError(
                "Invalid schema version history; restore a verified backup."
            )
        current = max(versions, default=0)
        if current > len(migrations):
            raise RuntimeError(
                f"Database schema {current} is newer than supported {len(migrations)}. Use a newer Storyroom."
            )
        if (
            not current
            and conn.execute(
                "SELECT 1 FROM sqlite_master WHERE name='projects'"
            ).fetchone()
        ):
            raise RuntimeError(
                "Existing database has no valid schema history; refusing to alter it."
            )
        if current and current < len(migrations):
            backup = path.with_name(
                f"{path.stem}.before-v{current + 1}.{uuid.uuid4().hex}.sqlite"
            )
            # A separate read connection sees the committed snapshot while our write
            # lock prevents concurrent updates. SQLite backup includes the WAL.
            with sqlite3.connect(path) as source, sqlite3.connect(backup) as target:
                source.backup(target)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_versions(version INTEGER PRIMARY KEY)"
        )
        for version in range(current + 1, len(migrations) + 1):
            # Refuse commit/rollback (including executescript's implicit commit)
            # from a migration so a faulty upgrade cannot escape atomic rollback.
            conn.set_authorizer(
                lambda action, *_: (
                    sqlite3.SQLITE_DENY
                    if action in (sqlite3.SQLITE_TRANSACTION, sqlite3.SQLITE_SAVEPOINT)
                    else sqlite3.SQLITE_OK
                )
            )
            try:
                migrations[version - 1](conn)
            finally:
                conn.set_authorizer(None)
            if not conn.in_transaction:
                raise RuntimeError("Migration ended its transaction unexpectedly")
            conn.execute("INSERT INTO schema_versions VALUES(?)", (version,))
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
