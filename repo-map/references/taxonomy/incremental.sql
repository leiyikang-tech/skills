-- incremental.sql — project_baselines store for the repo-map skill.
-- Purpose: "what do I know about THIS project?" so Refresh diffs against a
-- baseline instead of re-analyzing wholesale. Written after each successful
-- analysis; read at every run start to classify Fresh vs Refresh vs Same-domain.

CREATE TABLE IF NOT EXISTS project_baselines (
  repo_path         TEXT PRIMARY KEY,   -- absolute repo path
  last_analyzed_sha TEXT,               -- git HEAD the map was generated at
  paradigm_id       TEXT,               -- A1..A12 primary (axis A), for Same-domain dispatch
  artifacts         TEXT,               -- json: {root_kb, dirs[], profile, comparison}
  mapped_at         TEXT                -- ISO timestamp
);

CREATE INDEX IF NOT EXISTS idx_project_baselines_paradigm ON project_baselines(paradigm_id);