-- analysis_index.sql
-- Unified analysis registry for repo-map (including awesome-list mode).
-- Tracks which projects have been analyzed, by whom, and their
-- gap/opportunity status. Updated and persisted to the work-log
-- knowledge repo after every analysis run.
--
-- Apply to the shared analysis DB: {{ANALYSIS_DB}}
-- IMPORTANT: set busy_timeout BEFORE executescript, e.g.:
--   con = sqlite3.connect(db_path, timeout=10); con.execute("PRAGMA busy_timeout = 10000")
-- This protects against database is locked when multiple
-- /repo-map processes write concurrently.
--
-- ============================================================================
-- IMPORTANT: set busy_timeout BEFORE executescript, e.g.:
--   con = sqlite3.connect(db_path, timeout=10); con.execute("PRAGMA busy_timeout = 10000")
-- This protects against "database is locked" when multiple
-- /repo-map processes write concurrently.
PRAGMA busy_timeout = 10000;

-- ============================================================================
-- Unified analysis index: one row per analyzed project.
-- Bridges project_baselines (knowledge-map generated) + project_open_items
-- (gaps/opportunities) + sessions (analysis sessions) into a single
-- registry. The "analysis board" for what's been done and what's left.
-- ============================================================================
CREATE TABLE IF NOT EXISTS analysis_index (
  project_path    TEXT PRIMARY KEY,     -- canonical URL or local repo path
  project_name    TEXT,                   -- human-friendly display name
  source_list     TEXT DEFAULT '',        -- which awesome list it came from
  stars           INTEGER DEFAULT 0,      -- github stars (sort key)
  category        TEXT DEFAULT '',        -- awesome list category / domain
  paradigm_id     TEXT,                   -- A1..A12 (if classified by taxonomy)
  analyzed_at     TEXT,                   -- when analysis completed
  analysis_path   TEXT,                   -- work-log path: <topic>/<file>.md
  status          TEXT DEFAULT 'pending', -- pending | analyzed | failed | stale
  n_gaps          INTEGER DEFAULT 0,      -- count of associated gap items
  n_opportunities INTEGER DEFAULT 0,      -- count of associated opp items
  last_updated    TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_analysis_index_status   ON analysis_index(status);
CREATE INDEX IF NOT EXISTS idx_analysis_index_stars    ON analysis_index(stars DESC);
CREATE INDEX IF NOT EXISTS idx_analysis_index_domain   ON analysis_index(category);
CREATE INDEX IF NOT EXISTS idx_analysis_index_paradigm ON analysis_index(paradigm_id);

-- Convenience view: pending projects, sorted by stars (highest first).
-- This is the "what to analyze next" read for awesome-list mode.
CREATE VIEW IF NOT EXISTS v_analysis_pending AS
  SELECT project_path, project_name, source_list, stars, category,
         paradigm_id, status, n_gaps, n_opportunities
  FROM analysis_index
  WHERE status = 'pending'
  ORDER BY stars DESC;

-- Convenience view: analyzed projects (for audit / re-run).
CREATE VIEW IF NOT EXISTS v_analysis_done AS
  SELECT project_path, project_name, source_list, stars, category,
         analyzed_at, analysis_path, status, n_gaps, n_opportunities
  FROM analysis_index
  WHERE status = 'analyzed'
  ORDER BY analyzed_at DESC;
