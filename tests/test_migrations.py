import concurrent.futures
import sqlite3

import pytest

from server.migrations import MIGRATIONS, migrate
from server import db
from conftest import create_ready


def test_fresh_repeat_and_competing_startups(tmp_path):
    path = tmp_path / "db.sqlite"
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: migrate(path), range(4)))
    migrate(path)
    with sqlite3.connect(path) as c:
        assert c.execute("SELECT * FROM schema_versions").fetchall() == [(1,)]
        assert c.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert not list(tmp_path.glob("*.before-*.sqlite"))


def test_existing_project_survives_upgrade_and_backup(client, clip):
    pid, aid = create_ready(client, clip)
    board = [{"id": "section", "title": "Practice", "purpose": "", "selections": [
        {"id": "choice", "asset_id": aid, "moment_id": aid, "start_frame": 3, "end_frame": 20, "note": "Keep"}]}]
    assert client.put(f"/api/projects/{pid}/board", json={"revision": 0, "sections": board}).status_code == 200
    db.execute("INSERT INTO usage VALUES(?,?,?,?,?,?,?)", ("usage", None, "fixture", .1, .1, "settled", 1.0))
    db.execute("INSERT INTO feedback VALUES(?,?,?,?,?,?,?,?,?,?)",
               ("feedback", pid, aid, "brief", "Practice", 2, "useful", "{}", "group", 1.0))
    before = client.get(f"/api/projects/{pid}").json()
    from server import config
    path = config.DATA / "storyroom.sqlite"
    # Keep a WAL connection open so the backup must handle uncheckpointed pages.
    with sqlite3.connect(path) as keeper:
        keeper.execute("PRAGMA wal_autocheckpoint=0")
        keeper.execute("INSERT INTO cache VALUES('sentinel','retained')")
        keeper.commit()
        tables = ("projects", "revisions", "assets", "moments", "moment_fts", "jobs", "cache", "usage", "feedback")
        snapshots = {table: db.rows(f"SELECT * FROM {table}") for table in tables}
        migrate(path)  # Existing v1 adoption performs no data rewrite.
        def second(c):
            c.execute("CREATE TABLE upgrade_fixture(value TEXT)")
        migrate(path, (*MIGRATIONS, second))
        assert client.get(f"/api/projects/{pid}").json() == before
        assert {table: db.rows(f"SELECT * FROM {table}") for table in tables} == snapshots
        assert db.one("SELECT COUNT(*) AS n FROM revisions")["n"] > 0
        assert db.one("SELECT COUNT(*) AS n FROM moment_fts")["n"] == 1
        backup, = config.DATA.glob("*.before-v2.*.sqlite")
        with sqlite3.connect(backup) as saved:
            assert saved.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert saved.execute("SELECT value FROM cache").fetchone()[0] == "retained"
            assert saved.execute("SELECT board FROM projects").fetchone()[0] == db.one("SELECT board FROM projects")["board"]
            assert saved.execute("SELECT * FROM schema_versions").fetchall() == [(1,)]


def test_failed_upgrade_rolls_back_schema_data_and_version(tmp_path):
    path = tmp_path / "db.sqlite"
    migrate(path)
    def broken(c):
        c.execute("CREATE TABLE should_not_exist(value TEXT)")
        c.execute("INSERT INTO cache VALUES('bad','bad')")
        raise ValueError("injected")
    with pytest.raises(ValueError, match="injected"):
        migrate(path, (*MIGRATIONS, broken))
    with sqlite3.connect(path) as c:
        assert c.execute("SELECT * FROM schema_versions").fetchall() == [(1,)]
        assert not c.execute("SELECT * FROM cache").fetchall()
        assert not c.execute("SELECT name FROM sqlite_master WHERE name='should_not_exist'").fetchall()


def test_refuses_future_and_invalid_versions(tmp_path):
    path = tmp_path / "db.sqlite"
    migrate(path)
    with sqlite3.connect(path) as c:
        c.execute("INSERT INTO schema_versions VALUES(2)")
    with pytest.raises(RuntimeError, match="newer"):
        migrate(path)
    with sqlite3.connect(path) as c:
        c.execute("DELETE FROM schema_versions WHERE version=1")
    with pytest.raises(RuntimeError, match="Invalid"):
        migrate(path)


def test_migration_cannot_implicitly_commit(tmp_path):
    path = tmp_path / "db.sqlite"
    migrate(path)
    def unsafe(c):
        c.execute("CREATE TABLE rolled_back(value TEXT)")
        c.executescript("CREATE TABLE escaped(value TEXT);")
    with pytest.raises(sqlite3.DatabaseError):
        migrate(path, (*MIGRATIONS, unsafe))
    with sqlite3.connect(path) as c:
        assert not c.execute("SELECT name FROM sqlite_master WHERE name IN ('rolled_back','escaped')").fetchall()
        assert c.execute("SELECT * FROM schema_versions").fetchall() == [(1,)]
