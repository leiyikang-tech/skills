-- deepdive.sql  v1
-- Two-ontology + grounding schema for the repo-map `deep-dive` command.
-- Addresses the ground-truth audit (2026-09): the deep-dive design's
-- thinking-ontology and key-concept-ontology had NO persistence target.
-- This file gives them real, queryable tables, plus the grounding/citation
-- records that turn "the LLM claims it understands" into "the LLM grounded
-- the concept to a canonical Wikidata ID and verified the citation resolves."
--
-- Design principle (from the audit): NO node trusts the LLM's own judgment.
-- Every concept must carry a grounding_status (grounded via Wikidata SPARQL,
-- or flagged hallucination). Every claim must carry a citation that resolves.
-- Every methodology record follows Mem0's procedural-memory structure
-- (objective / steps / results / findings / errors) so it is queryable, not
-- free-text prose.
--
-- Apply to the shared board DB: {{ANALYSIS_DB}}
-- IMPORTANT: set busy_timeout BEFORE executescript (concurrency), e.g.:
--   con = sqlite3.connect(db_path, timeout=10); con.execute("PRAGMA busy_timeout = 10000")
-- Apply:  sqlite3 {{ANALYSIS_DB}} < deepdive.sql

PRAGMA busy_timeout = 10000;

-- ============================================================================
-- KEY-CONCEPT ONTOLOGY (关键概念本体)
-- One row per concept the deep-dive establishes. `wiki_qid` is the canonical
-- Wikidata identifier the concept grounded to. A concept with
-- grounding_status NOT IN ('grounded','partial') was NOT trusted into the
-- ontology (it either failed grounding or was flagged a hallucination).
-- `mechanism` is the bottom-layer mechanism (API/algorithm/protocol), the
-- anti-hallucination contract from Op3.
-- ============================================================================
CREATE TABLE IF NOT EXISTS deepdive_concepts (
  concept_id        TEXT PRIMARY KEY,     -- cc-<project>-<n>
  project_path      TEXT,                 -- FK -> analysis_index.project_path
  name              TEXT,                 -- concept name
  mechanism         TEXT DEFAULT '',      -- bottom-layer mechanism (API/algo/protocol)
  paradigm_id       TEXT,                 -- A1..A12 (if classified)
  wiki_qid          TEXT DEFAULT '',      -- canonical Wikidata QID (grounding result)
  wiki_label        TEXT DEFAULT '',      -- Wikidata label resolved
  wiki_url          TEXT DEFAULT '',      -- en.wikipedia.org / wikidata.org link
  grounding_status  TEXT DEFAULT 'pending', -- grounded | partial | not_found | hallucination
  source_evidence   TEXT DEFAULT '',      -- the code/text snippet the concept was extracted from
  created_at        TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_dd_concepts_project ON deepdive_concepts(project_path);
CREATE INDEX IF NOT EXISTS idx_dd_concepts_qid     ON deepdive_concepts(wiki_qid);
CREATE INDEX IF NOT EXISTS idx_dd_concepts_ground   ON deepdive_concepts(grounding_status);
CREATE INDEX IF NOT EXISTS idx_dd_concepts_paradigm ON deepdive_concepts(paradigm_id);

-- ============================================================================
-- CITATION RECORDS (引用 + URL 解析校验)
-- Every claim written to the ontology must carry a citation whose URL was
-- actually resolved (verify_status='resolves') before the claim is trusted.
-- A claim whose citation never resolves is not ground truth.
-- ============================================================================
CREATE TABLE IF NOT EXISTS deepdive_citations (
  citation_id   TEXT PRIMARY KEY,         -- ct-<project>-<n>
  project_path  TEXT,
  concept_id    TEXT,                     -- FK -> deepdive_concepts
  claim         TEXT DEFAULT '',
  source_url    TEXT DEFAULT '',          -- arXiv/DOI/wiki/web/github
  source_type   TEXT DEFAULT 'web',       -- arxiv | doi | wiki | web | github
  url_verified  INTEGER DEFAULT 0,        -- 0=not yet resolved, 1=URL resolves
  verify_status TEXT DEFAULT 'unverified',-- unverified | resolves | broken | not_found
  verified_at   TEXT,
  created_at    TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_dd_citations_concept ON deepdive_citations(concept_id);
CREATE INDEX IF NOT EXISTS idx_dd_citations_status  ON deepdive_citations(verify_status);
CREATE INDEX IF NOT EXISTS idx_dd_citations_project ON deepdive_citations(project_path);

-- ============================================================================
-- THINKING / METHODOLOGY ONTOLOGY (思维本体)
-- Follows Mem0's PROCEDURAL_MEMORY structure so methodology is a queryable
-- record, not free-text prose. One row per deep-dive LAYER. `run_id` links to
-- deepdive_runs for the convergence + regression audit.
-- ============================================================================
CREATE TABLE IF NOT EXISTS deepdive_methods (
  method_id     TEXT PRIMARY KEY,         -- dd-<project>-L<n>
  project_path  TEXT,
  run_id        TEXT DEFAULT '',          -- FK -> deepdive_runs
  layer         INTEGER DEFAULT 1,        -- deep-dive layer number
  objective     TEXT DEFAULT '',          -- this layer's goal (Task Objective)
  steps         TEXT DEFAULT '',          -- numbered actions (Sequential Actions)
  action_result TEXT DEFAULT '',          -- verbatim action results
  findings      TEXT DEFAULT '',          -- Key Findings
  errors        TEXT DEFAULT '',          -- Errors & Challenges
  context       TEXT DEFAULT '',          -- Current Context snapshot
  created_at    TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_dd_methods_project ON deepdive_methods(project_path);
CREATE INDEX IF NOT EXISTS idx_dd_methods_run     ON deepdive_methods(run_id);
CREATE INDEX IF NOT EXISTS idx_dd_methods_layer   ON deepdive_methods(layer);

-- ============================================================================
-- CROSS-LAYER FINDINGS (跨层关键发现, queryable)
-- A finding that accumulates ≥3 converging independent analyses becomes an
-- Op4 opportunity seed (the MIN_CONVERGENCE_COUNT contract). `grounded_qid`
-- is the Wikidata QID if the finding's central concept grounded.
-- ============================================================================
CREATE TABLE IF NOT EXISTS deepdive_findings (
  finding_id     TEXT PRIMARY KEY,        -- fd-<project>-L<n>-<m>
  project_path   TEXT,
  run_id         TEXT DEFAULT '',
  layer          INTEGER DEFAULT 1,
  claim          TEXT DEFAULT '',         -- the finding assertion
  evidence_type  TEXT DEFAULT '',         -- code | paper | wiki | web | gap
  citation       TEXT DEFAULT '',         -- the grounded citation (source_url)
  grounded_qid   TEXT DEFAULT '',         -- Wikidata QID if applicable
  verified       INTEGER DEFAULT 0,       -- 0=unverified 1=externally verified
  created_at     TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_dd_findings_project ON deepdive_findings(project_path);
CREATE INDEX IF NOT EXISTS idx_dd_findings_claim   ON deepdive_findings(claim);

-- ============================================================================
-- ERROR PATTERNS (错误模式, 防复发)
-- The recursive self-improvement write-back target. Each error carries a
-- `lesson`; a recurring error (recurring=1) is a blind-spot the methodology
-- must fix. The regression check (harness/regression_check.py) verifies the
-- fix actually reduced recurrences before the playbook is updated.
-- ============================================================================
CREATE TABLE IF NOT EXISTS deepdive_errors (
  error_id      TEXT PRIMARY KEY,         -- er-<project>-L<n>-<m>
  project_path  TEXT,
  run_id        TEXT DEFAULT '',
  layer         INTEGER DEFAULT 1,
  error_type    TEXT DEFAULT '',          -- concept | search | gap | method
  message       TEXT DEFAULT '',          -- the error message
  lesson        TEXT DEFAULT '',          -- what was learned (blind-spot)
  recurring     INTEGER DEFAULT 0,        -- 0=first 1=recurring (blind-spot)
  created_at    TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_dd_errors_project ON deepdive_errors(project_path);
CREATE INDEX IF NOT EXISTS idx_dd_errors_type    ON deepdive_errors(error_type);

-- ============================================================================
-- RUN AUDIT (每层运行审计 + 收敛 + 回归)
-- The convergence check (harness/convergence.py) queries this table: a run
-- converges when a LATER run on the same project yields no new grounded
-- concepts / no new findings / no new open-item fills (SQL-checkable, not
-- "the LLM feels stable"). The regression check compares gate-pass rates
-- across runs before/after a playbook change.
-- ============================================================================
CREATE TABLE IF NOT EXISTS deepdive_runs (
  run_id          TEXT PRIMARY KEY,       -- run-<project>-<ts>
  project_path    TEXT,
  layer           INTEGER DEFAULT 1,
  started_at      TEXT DEFAULT (datetime('now')),
  finished_at     TEXT,
  n_concepts      INTEGER DEFAULT 0,      -- grounded concepts this layer
  n_findings      INTEGER DEFAULT 0,
  n_citations     INTEGER DEFAULT 0,
  n_gaps_claimed  INTEGER DEFAULT 0,      -- project_open_items claimed
  n_gaps_filled   INTEGER DEFAULT 0,      -- project_open_items filled
  gate_verdict    TEXT DEFAULT 'PENDING', -- Q1-Q5 verdict for this layer
  converged       INTEGER DEFAULT 0       -- 1 when this layer is a convergence point
);

CREATE INDEX IF NOT EXISTS idx_dd_runs_project ON deepdive_runs(project_path);
CREATE INDEX IF NOT EXISTS idx_dd_runs_layer   ON deepdive_runs(layer);

-- ============================================================================
-- Convergence query (SQL-checkable stop condition; NOT "score stable").
-- A project has converged when the LAST run added zero new grounded concepts,
-- zero new findings, and zero new open-item fills versus the run before it.
-- ============================================================================
CREATE VIEW IF NOT EXISTS v_dd_convergence AS
  SELECT
    r1.project_path,
    r1.run_id AS last_run,
    r1.layer AS last_layer,
    r1.finished_at,
    CASE
      WHEN r1.n_concepts = 0 AND r1.n_findings = 0
           AND r1.n_gaps_claimed = 0 AND r1.n_gaps_filled = 0
        THEN 1
      ELSE 0
    END AS converged
  FROM deepdive_runs r1
  WHERE r1.layer = (
    SELECT MAX(r2.layer) FROM deepdive_runs r2
    WHERE r2.project_path = r1.project_path
  );