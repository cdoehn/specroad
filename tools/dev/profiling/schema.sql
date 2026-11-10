CREATE TABLE metadata (id INTEGER PRIMARY KEY CHECK(id=1), marker TEXT NOT NULL, version INTEGER NOT NULL);
INSERT INTO metadata VALUES (1, 'specroad-test-profiles', 1);
CREATE TABLE runs (
    id TEXT PRIMARY KEY, repository TEXT NOT NULL, directory TEXT NOT NULL UNIQUE,
    created TEXT NOT NULL, finished TEXT, status TEXT NOT NULL,
    source_sha256 TEXT, selection_sha256 TEXT, settings_json TEXT NOT NULL,
    workers INTEGER, command_json TEXT, exit_code INTEGER, error TEXT
);
CREATE TABLE tests (
    run_id TEXT NOT NULL REFERENCES runs(id), nodeid TEXT NOT NULL, test_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL, historical_json TEXT, status TEXT NOT NULL DEFAULT 'selected',
    worker TEXT, pid INTEGER, tid INTEGER, cpu INTEGER, started_ns INTEGER, finished_ns INTEGER,
    outcome TEXT, PRIMARY KEY(run_id,nodeid), UNIQUE(run_id,test_id)
);
CREATE TABLE phases (
    id INTEGER PRIMARY KEY, run_id TEXT NOT NULL, nodeid TEXT NOT NULL,
    phase TEXT NOT NULL CHECK(phase IN ('setup','call','teardown')),
    pid INTEGER NOT NULL, tid INTEGER NOT NULL, start_ns INTEGER NOT NULL, end_ns INTEGER NOT NULL,
    elapsed_ns INTEGER NOT NULL CHECK(elapsed_ns>=0), resources_json TEXT NOT NULL,
    outcome TEXT, UNIQUE(run_id,nodeid,phase),
    FOREIGN KEY(run_id,nodeid) REFERENCES tests(run_id,nodeid)
);
CREATE TABLE python_functions (
    phase_id INTEGER NOT NULL REFERENCES phases(id), function_id INTEGER NOT NULL,
    filename TEXT NOT NULL, line INTEGER NOT NULL, name TEXT NOT NULL,
    primitive_calls INTEGER NOT NULL, calls INTEGER NOT NULL,
    self_seconds REAL NOT NULL, cumulative_seconds REAL NOT NULL,
    PRIMARY KEY(phase_id,function_id)
);
CREATE TABLE python_callers (
    phase_id INTEGER NOT NULL, function_id INTEGER NOT NULL,
    filename TEXT NOT NULL, line INTEGER NOT NULL, name TEXT NOT NULL,
    primitive_calls INTEGER NOT NULL, calls INTEGER NOT NULL,
    self_seconds REAL NOT NULL, cumulative_seconds REAL NOT NULL,
    FOREIGN KEY(phase_id,function_id) REFERENCES python_functions(phase_id,function_id)
);
CREATE TABLE artifacts (
    id INTEGER PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id),
    path TEXT NOT NULL, kind TEXT NOT NULL, nodeid TEXT, pid INTEGER,
    state TEXT NOT NULL, codec TEXT NOT NULL DEFAULT 'zlib-chunks-v1',
    byte_count INTEGER, sha256 TEXT, UNIQUE(run_id,path)
);
CREATE TABLE artifact_chunks (
    artifact_id INTEGER NOT NULL REFERENCES artifacts(id), ordinal INTEGER NOT NULL,
    raw_size INTEGER NOT NULL, data BLOB NOT NULL, PRIMARY KEY(artifact_id,ordinal)
);
CREATE INDEX tests_status ON tests(run_id,status);
CREATE INDEX phases_time ON phases(run_id,pid,tid,start_ns,end_ns);
CREATE INDEX python_hotspots ON python_functions(phase_id,self_seconds DESC);
CREATE INDEX artifacts_run ON artifacts(run_id,kind);
