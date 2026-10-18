-- refcode.sql - reference schema for the reusable reference-code database.
-- Single source of truth is the SCHEMA constant in refcode.py; this file is the
-- human-readable mirror (kept in sync by hand). Apply with:
--     sqlite3 /root/.sisyphus/db/refcode.db < refcode.sql
-- `refcode dump --out refcode.dump.sql` produces a git-friendly data dump.

PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- corpus registry: the shareable / pinnable / reviewable artifact
-- (= XERJ corpus.json equivalent). Contains NO source, only pointers.
CREATE TABLE IF NOT EXISTS ref_projects (
  slug             TEXT PRIMARY KEY,
  url              TEXT,
  sha              TEXT,              -- 40-hex pinned commit, NULL for local dirs
  licence          TEXT,
  use_policy       TEXT,              -- adapt-with-attribution | approach-only | mixed
  domain           TEXT,              -- classified domain (heuristic, see docs)
  languages        TEXT,              -- JSON array
  ask_for          TEXT,
  dependency_names TEXT,              -- JSON array of crate/npm/go/pypi names
  status           TEXT DEFAULT 'live',
  quality_grade    TEXT,
  local_path       TEXT,
  bytes            INTEGER,
  files            INTEGER,
  symbols          INTEGER,
  windows          INTEGER,
  indexed_at       TEXT,
  refreshed_at     TEXT
);

-- symbols across all projects: the "defs" arm (exact + prefix lookup)
CREATE TABLE IF NOT EXISTS ref_symbols (
  project        TEXT NOT NULL,
  node_id        TEXT NOT NULL,
  kind           TEXT,
  name           TEXT,
  qualified_name TEXT,
  file_path      TEXT,
  language       TEXT,
  start_line     INTEGER,
  end_line       INTEGER,
  signature      TEXT,
  docstring      TEXT,
  PRIMARY KEY (project, node_id)
);
CREATE INDEX IF NOT EXISTS idx_refsym_name  ON ref_symbols(name);
CREATE INDEX IF NOT EXISTS idx_refsym_proj  ON ref_symbols(project);
CREATE INDEX IF NOT EXISTS idx_refsym_qual  ON ref_symbols(qualified_name);

-- body windows: the "body" arm (FTS5 => BM25 for free)
CREATE VIRTUAL TABLE IF NOT EXISTS ref_body_fts USING fts5(
  project   UNINDEXED,
  file_path,
  language  UNINDEXED,
  win       UNINDEXED,
  line0     UNINDEXED,
  body,
  tokenize = 'unicode61'
);

-- docs about corpora / projects
CREATE TABLE IF NOT EXISTS ref_docs (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  slug      TEXT,
  kind      TEXT,
  title     TEXT,
  body      TEXT,
  created_at TEXT
);
