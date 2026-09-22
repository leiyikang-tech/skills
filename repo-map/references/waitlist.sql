-- repo-map: waitlist extension for analysis_index.
-- awesome-list mode now enqueues candidate projects into a WAITLIST instead of
-- deep-analyzing every one. We EXTEND analysis_index (the single project board)
-- rather than create a parallel waitlist table -- same lesson as the
-- project_open_items unification: one board, waitlisted is just a status.
--
--   status='waitlisted'  -> recorded with core functions, not yet deep-analyzed
--   status='analyzed'    -> full Op1-Op5 done
--   status='pending'     -> parsed, awaiting classification
--   status='failed'      -> clone/analysis error
--   status='stale'       -> analyzed but repo has moved on (Refresh pending)
--
-- Apply: sqlite3 {{ANALYSIS_DB}} < waitlist.sql

ALTER TABLE analysis_index ADD COLUMN core_functions TEXT DEFAULT '';
ALTER TABLE analysis_index ADD COLUMN why_worth      TEXT DEFAULT '';
-- source_type (github|arxiv|blog|web) drives the pull-to-analyze branch:
-- github/.git -> clone + Op1-Op5; arxiv/blog -> paper deep-analysis path.
ALTER TABLE analysis_index ADD COLUMN source_type     TEXT DEFAULT 'github';
-- v2 analysis-value score (0..1). Drives waitlist sort order -- stars are a
-- tiebreaker, NOT the sort key. See op1-init-deep.md Phase 2 for the formula:
--   value = .35*gap_fill + .20*paradigm_relevance + .25*novelty + .15*atomic_value + .05*maintenance
ALTER TABLE analysis_index ADD COLUMN value_score     REAL DEFAULT 0;
-- per-dimension component scores (0..1) so waitlist can sort by ANY axis,
-- not just the aggregate. v_maintenance = log10(1+stars) normalized.
ALTER TABLE analysis_index ADD COLUMN v_gap_fill   REAL DEFAULT 0;
ALTER TABLE analysis_index ADD COLUMN v_paradigm   REAL DEFAULT 0;
ALTER TABLE analysis_index ADD COLUMN v_novelty    REAL DEFAULT 0;
ALTER TABLE analysis_index ADD COLUMN v_atomic     REAL DEFAULT 0;
ALTER TABLE analysis_index ADD COLUMN v_maintenance REAL DEFAULT 0;

-- 'waitlisted' flag drives the awesome-mode pull-to-analyze workflow.
UPDATE analysis_index SET status='waitlisted' WHERE status='pending' AND core_functions != '';

CREATE INDEX idx_analysis_index_waitlist ON analysis_index(status);
CREATE INDEX idx_analysis_index_value    ON analysis_index(value_score DESC);