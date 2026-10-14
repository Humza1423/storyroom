CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY,name TEXT NOT NULL,brief TEXT NOT NULL DEFAULT '',
          board TEXT NOT NULL DEFAULT '[]',revision INTEGER NOT NULL DEFAULT 0,created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS revisions(project_id TEXT NOT NULL,revision INTEGER NOT NULL,board TEXT NOT NULL,
          PRIMARY KEY(project_id,revision));
        CREATE TABLE IF NOT EXISTS assets(id TEXT PRIMARY KEY,project_id TEXT NOT NULL REFERENCES projects(id),
          name TEXT NOT NULL,hash TEXT NOT NULL,bytes INTEGER NOT NULL,duration REAL NOT NULL,frames INTEGER NOT NULL,
          width INTEGER NOT NULL,height INTEGER NOT NULL,has_audio INTEGER NOT NULL,status TEXT NOT NULL,
          error TEXT,provenance TEXT NOT NULL DEFAULT '{}',UNIQUE(project_id,hash));
        CREATE TABLE IF NOT EXISTS moments(id TEXT PRIMARY KEY,asset_id TEXT NOT NULL REFERENCES assets(id),
          start_frame INTEGER NOT NULL,end_frame INTEGER NOT NULL,description TEXT NOT NULL,source TEXT NOT NULL,
          uncertainty TEXT NOT NULL DEFAULT '',embedding TEXT,embedding_model TEXT);
        CREATE VIRTUAL TABLE IF NOT EXISTS moment_fts USING fts5(id UNINDEXED,description);
        CREATE TRIGGER IF NOT EXISTS moments_insert AFTER INSERT ON moments BEGIN
          INSERT INTO moment_fts(id,description) VALUES(new.id,new.description); END;
        CREATE TRIGGER IF NOT EXISTS moments_delete AFTER DELETE ON moments BEGIN
          DELETE FROM moment_fts WHERE id=old.id; END;
        CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,project_id TEXT NOT NULL REFERENCES projects(id),
          kind TEXT NOT NULL,payload TEXT NOT NULL,status TEXT NOT NULL,progress REAL NOT NULL DEFAULT 0,
          message TEXT NOT NULL DEFAULT '',result TEXT,created REAL NOT NULL,started REAL,finished REAL,cancel INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS cache(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS usage(id TEXT PRIMARY KEY,job_id TEXT,model TEXT NOT NULL,reserved REAL NOT NULL,
          actual REAL,status TEXT NOT NULL,created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS feedback(id TEXT PRIMARY KEY,project_id TEXT NOT NULL,moment_id TEXT NOT NULL,
          brief TEXT NOT NULL,section TEXT NOT NULL,rating INTEGER NOT NULL,reason TEXT NOT NULL,
          features TEXT NOT NULL,footage_group TEXT NOT NULL,created REAL NOT NULL);
