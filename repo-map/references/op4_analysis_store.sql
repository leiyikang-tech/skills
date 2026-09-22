-- op4_analysis_store.sql  v2
-- Unified gap/opportunity registry for Op4 of the repo-map skill.
-- Apply to the shared analysis DB: {{ANALYSIS_DB}}
--
-- DESIGN CHANGE (v2): merged separate project_gaps + project_opportunities
-- into ONE unified project_open_items table. Rationale (user request):
--   split tables gave no lifecycle tracking -- no "who needs this",
--   no "when will it be analyzed", no "when was it filled".
--   A single table with a `kind` column + status machine makes the
--   full "demand -> analyze -> fill -> verify" loop queryable.
-- Each row = ONE demand item (gap OR opp), with a complete lifecycle.
-- Apply:  sqlite3 {{ANALYSIS_DB}} < op4_analysis_store.sql

-- A-paradigm registry mirror (taxonomy Axis A). `domain` SHOULD be an
-- A-paradigm id (A1..A12) when applicable; legacy rows may carry
-- project-level domain names -- preserved as-is.
CREATE TABLE IF NOT EXISTS project_paradigms (
  paradigm_id  TEXT PRIMARY KEY,
  name_zh      TEXT,
  name_en      TEXT,
  dispatch     TEXT,
  worklog_bins TEXT,
  ext_note     TEXT DEFAULT ''
);

INSERT OR IGNORE INTO project_paradigms
  (paradigm_id, name_zh, name_en, dispatch, worklog_bins, ext_note) VALUES
  ('A1','Agent 框架与编排','Agent framework & orchestration','mixed','智能体框架,agentos,hermes-harness,skillsos',''),
  ('A2','检索增强 / RAG','Retrieval-Augmented Generation','mixed','数据和知识清洗,本体工程/rag,cangjie-skill',''),
  ('A3','记忆与进化','Memory & self-evolution','papers','记忆和进化',''),
  ('A4','本体与知识图谱','Ontology & knowledge graph','mixed','本体工程',''),
  ('A5','推理与推理优化','Reasoning & inference optimization','papers','推理优化,coding/幻觉',''),
  ('A6','NL2SQL / 数据智能体','NL2SQL / data agent','competitor','text2sql,data',''),
  ('A7','安全与合规','Security & compliance','standards','安全,智能体框架/企业一站式AI/参考规范',''),
  ('A8','协作与多智能体','Collaboration & multi-agent (human-AI)','competitor','AI协作分析',''),
  ('A9','评估与评测','Evaluation & benchmarking','mixed','agentos/评估工程,评测基准',''),
  ('A10','工具与执行层','Tools & execution layer','competitor','tools,devops,aiapp,office',''),
  ('A11','深度研究 / 科学知识','Deep research / AI4S','papers','深度研究,research-kb',''),
  ('A12','前端 / UI 呈现','Front-end / UI presentation','competitor','前端框架,office,demo/需求到原型','');

-- ============================================================================
-- Unified demand board: ONE table for ALL open gap/opportunity items.
-- `kind` distinguishes gap vs opp; `extra` JSON carries type-specific
-- attributes (severity/gap_type for gaps; type/confidence/direction for opps).
-- Status machine: discovered -> analyzing -> filled | skipped | closed.
-- ============================================================================
CREATE TABLE IF NOT EXISTS project_open_items (
  item_id              TEXT PRIMARY KEY,
  kind                 TEXT NOT NULL,
  domain               TEXT DEFAULT 'uncategorized',
  description          TEXT,
  priority             REAL,
  needer               TEXT DEFAULT '',
  status               TEXT DEFAULT 'discovered',
  discovered_at        TEXT,
  scheduled_at         TEXT,
  analyzed_at          TEXT,
  filled_by_project    TEXT,
  filled_at            TEXT,
  fill_progress        REAL DEFAULT 0,
  tags                 TEXT,
  originating_project  TEXT,
  extra                TEXT
);

CREATE INDEX IF NOT EXISTS idx_open_items_priority ON project_open_items(priority DESC);
CREATE INDEX IF NOT EXISTS idx_open_items_domain   ON project_open_items(domain);
CREATE INDEX IF NOT EXISTS idx_open_items_status   ON project_open_items(status);
CREATE INDEX IF NOT EXISTS idx_open_items_needer   ON project_open_items(needer);

-- Convenience view: open items, sorted by priority (the "持续关注" read).
CREATE VIEW IF NOT EXISTS v_op4_open_items AS
  SELECT item_id, kind, domain, description, priority,
         needer, status, discovered_at, scheduled_at,
         fill_progress, tags, originating_project
  FROM project_open_items
  WHERE status IN ('discovered','analyzing')
  ORDER BY priority DESC;

-- Convenience view: the closed/filled history (auditing).
CREATE VIEW IF NOT EXISTS v_op4_filled_items AS
  SELECT item_id, kind, domain, description, priority,
         needer, filled_by_project, filled_at, fill_progress, tags
  FROM project_open_items
  WHERE status IN ('filled','skipped','closed')
  ORDER BY filled_at DESC;

-- ============================================================================
-- Migration: old project_gaps / project_opportunities -> project_open_items.
-- Read from old tables FIRST, then drop them. Run ONCE (idempotent).
-- ============================================================================
INSERT OR IGNORE INTO project_open_items
  (item_id, kind, domain, description, priority, needer, status,
   discovered_at, fill_progress, tags, originating_project, extra)
  SELECT gap_id, 'gap', domain, description, priority, '',
    CASE WHEN progress >= 0.9 THEN 'filled' ELSE 'discovered' END,
    discovered_at, progress, tags, originating_project,
    json_object('gap_type', gap_type, 'severity', severity, 'demand_weight', demand_weight)
  FROM project_gaps;

INSERT OR IGNORE INTO project_open_items
  (item_id, kind, domain, description, priority, needer, status,
   discovered_at, fill_progress, tags, originating_project, extra)
  SELECT opp_id, 'opp', domain, description, confidence, '', 'discovered',
    discovered_at, confidence, tags, originating_project,
    json_object('type', type, 'direction', direction, 'confidence', confidence)
  FROM project_opportunities;

DROP TABLE IF EXISTS project_opportunities;
DROP TABLE IF EXISTS project_gaps;
